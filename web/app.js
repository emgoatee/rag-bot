const stepElements = Array.from(document.querySelectorAll(".step"));
const toast = document.getElementById("toast");
const fileTableBody = document.getElementById("file-table-body");
const storeMeta = document.getElementById("store-meta");
const chatThread = document.getElementById("chat-thread");
const messageTemplate = document.getElementById("message-template");
const uploadStatus = document.getElementById("upload-status");
const selectedFilesList = document.getElementById("selected-files");
const uploadProgress = document.getElementById("upload-progress");
const modelHub = document.getElementById("model-hub");
const modelList = document.getElementById("model-list");
const workflowSection = document.getElementById("workflow");
const backToModelsBtn = document.getElementById("back-to-models");
const createStoreBtn = document.getElementById("create-store-btn");
const createStoreModal = document.getElementById("create-store-modal");
const createStoreForm = document.getElementById("create-store-form");
const cancelStoreBtn = document.getElementById("cancel-store-btn");
const storeNameInput = document.getElementById("store-name-input");

let currentStep = 1;
let hasUploaded = false;
let recentUploads = [];
const operationStates = new Map();
let currentStoreId = localStorage.getItem("selectedStoreId") || null;
let availableStores = [];

const setStep = (index) => {
  currentStep = index;
  stepElements.forEach((step, idx) => {
    step.classList.toggle("active", idx === index - 1);
    step.classList.toggle("completed", idx < index - 1);
  });
};

const updateStoreMeta = (messageOrParts) => {
  if (!storeMeta) return;
  if (Array.isArray(messageOrParts)) {
    const filtered = messageOrParts.filter(Boolean);
    storeMeta.textContent = filtered.join(" • ");
    return;
  }
  storeMeta.textContent = messageOrParts;
};

const getStoreDisplayName = (storeId) => {
  if (!storeId) return "Model";
  const store = availableStores.find((entry) => entry.name === storeId);
  if (store) {
    return store.display_name || (store.name ? store.name.split("/").pop() : "Model");
  }
  return storeId.split("/").pop() || storeId;
};

const showModelHub = () => {
  if (modelHub) {
    modelHub.classList.remove("hidden");
  }
  if (workflowSection) {
    workflowSection.classList.add("hidden");
  }
  if (backToModelsBtn) {
    backToModelsBtn.classList.add("hidden");
  }
  setStep(1);
  updateStoreMeta(
    availableStores.length
      ? "Select a model to continue."
      : "No models yet. Create one to get started."
  );
  renderModelList();
};

const showWorkflow = () => {
  if (modelHub) {
    modelHub.classList.add("hidden");
  }
  if (workflowSection) {
    workflowSection.classList.remove("hidden");
  }
  if (backToModelsBtn) {
    backToModelsBtn.classList.remove("hidden");
  }
};

const updateUploadStatus = (message, variant) => {
  if (!uploadStatus) return;
  uploadStatus.textContent = message || "";
  uploadStatus.classList.remove("active", "success", "error");
  if (variant) {
    uploadStatus.classList.add(variant);
  }
};

const renderSelectedFiles = (files) => {
  if (!selectedFilesList) return;
  selectedFilesList.innerHTML = "";
  const submitButton = document.querySelector("#file-upload-form button[type='submit']");
  const hasFiles = files && files.length;
  if (submitButton) {
    submitButton.disabled = !hasFiles;
  }
  if (!hasFiles) {
    selectedFilesList.classList.add("hidden");
    return;
  }
  files.forEach((file) => {
    const li = document.createElement("li");
    li.textContent = file.name;
    selectedFilesList.appendChild(li);
  });
  selectedFilesList.classList.remove("hidden");
};

const renderUploadProgress = () => {
  if (!uploadProgress) return;
  uploadProgress.innerHTML = "";
  if (operationStates.size === 0) return;

  for (const [, details] of operationStates.entries()) {
    const item = document.createElement("div");
    item.className = `status-item ${details.status}`;

    const label =
      details.friendlyName ||
      details.name ||
      (details.documentPath ? details.documentPath.split("/").pop() : "Document");

    const pill = document.createElement("span");
    pill.className = "status-pill";
    pill.textContent =
      details.status === "processing"
        ? "Indexing"
        : details.status === "success"
        ? "Ready"
        : "Error";

    const message = document.createElement("span");
    if (details.status === "error" && details.error) {
      message.textContent = `${label}: ${details.error}`;
    } else if (details.status === "success") {
      message.textContent = `${label} indexed.`;
    } else {
      message.textContent = `${label} is processing…`;
    }

    item.appendChild(pill);
    item.appendChild(message);
    uploadProgress.appendChild(item);
  }
};

const scheduleOperationPoll = (operationName) => {
  const poll = async () => {
    const entry = operationStates.get(operationName);
    if (!entry || entry.status === "success" || entry.status === "error") {
      return;
    }
    try {
      const response = await fetch(
        `/operation-status?name=${encodeURIComponent(operationName)}`
      );
      if (!response.ok) throw new Error(await response.text());
      const payload = await response.json();

      if (payload.done) {
        entry.status = payload.error ? "error" : "success";
        entry.error = payload.error || null;
        entry.documentPath = payload.document_name || entry.documentPath;
        entry.name =
          payload.display_name ||
          entry.name ||
          (entry.documentPath ? entry.documentPath.split("/").pop() : entry.name);
        renderUploadProgress();
        if (!payload.error) {
          await fetchFiles();
        }
        return;
      }

      entry.status = "processing";
      renderUploadProgress();
    } catch (error) {
      const entry = operationStates.get(operationName);
      if (entry) {
        entry.status = "error";
        entry.error = error.message;
        renderUploadProgress();
      }
      return;
    }

    setTimeout(poll, 4000);
  };

  setTimeout(poll, 4000);
};

const showToast = (message, variant = "info") => {
  toast.textContent = message;
  toast.dataset.variant = variant || "info";
  toast.classList.add("visible");
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => {
    toast.classList.remove("visible");
  }, 3700);
};

// Store Management Functions
const loadStores = async () => {
  try {
    const response = await fetch("/stores");
    if (!response.ok) throw new Error(await response.text());
    const payload = await response.json();
    availableStores = payload.stores || [];
    renderModelList();

    if (!availableStores.length) {
      currentStoreId = null;
      localStorage.removeItem("selectedStoreId");
      showModelHub();
      return;
    }

    if (currentStoreId) {
      const exists = availableStores.some((store) => store.name === currentStoreId);
      if (exists) {
        await selectStore(currentStoreId, { preserveState: true });
        return;
      }
      currentStoreId = null;
      localStorage.removeItem("selectedStoreId");
    }

    showModelHub();
  } catch (error) {
    showToast(`Unable to load models: ${error.message}`, "error");
    if (modelList) {
      modelList.innerHTML = "";
      const errorCard = document.createElement("div");
      errorCard.className = "model-empty";
      errorCard.textContent = `Unable to load models. ${error.message}`;
      modelList.appendChild(errorCard);
    }
    showModelHub();
  }
};

const createStore = async (displayName) => {
  try {
    const response = await fetch("/stores", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ display_name: displayName }),
    });
    if (!response.ok) throw new Error(await response.text());
    const payload = await response.json();
    const newStore = payload.store;

    availableStores.push(newStore);
    renderModelList();
    await selectStore(newStore.name);
    showToast(`Model "${displayName}" created successfully!`, "success");
    return newStore;
  } catch (error) {
    showToast(`Failed to create model: ${error.message}`, "error");
    throw error;
  }
};

const formatBytes = (bytes) => {
  if (!bytes) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let idx = 0;
  let value = bytes;
  while (value >= 1024 && idx < units.length - 1) {
    value /= 1024;
    idx += 1;
  }
  return `${value.toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`;
};

const formatDate = (isoString) => {
  if (!isoString) return "—";
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return isoString;
  return date.toLocaleString();
};

const updateActiveStoreMeta = (extraParts = []) => {
  if (!currentStoreId) return;
  const parts = [`Active model: ${getStoreDisplayName(currentStoreId)}`];
  if (Array.isArray(extraParts)) {
    parts.push(...extraParts.filter(Boolean));
  } else if (extraParts) {
    parts.push(extraParts);
  }
  updateStoreMeta(parts);
};

const renderModelList = () => {
  if (!modelList) return;

  modelList.innerHTML = "";
  if (!availableStores.length) {
    const empty = document.createElement("div");
    empty.className = "model-empty";
    empty.innerHTML =
      "No models yet. Create a model to upload documents and start chatting.";
    modelList.appendChild(empty);
    return;
  }

  const sortedStores = [...availableStores].sort((a, b) => {
    const aTime = new Date(a.update_time || a.create_time || 0).getTime();
    const bTime = new Date(b.update_time || b.create_time || 0).getTime();
    return bTime - aTime;
  });

  sortedStores.forEach((store) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "model-card";
    if (store.name === currentStoreId) {
      card.classList.add("active");
    }

    const displayName =
      store.display_name || (store.name ? store.name.split("/").pop() : "Model");
    const shortId = store.name ? store.name.split("/").pop() : "—";
    const updated = formatDate(store.update_time || store.create_time);
    const updatedLabel = updated === "—" ? "No activity yet" : `Updated ${updated}`;

    card.innerHTML = `
      <div class="model-name">${displayName}</div>
      <div class="model-meta">${shortId}</div>
      <div class="model-updated">${updatedLabel}</div>
    `;

    card.addEventListener("click", () => {
      selectStore(store.name);
    });

    modelList.appendChild(card);
  });
};

const selectStore = async (storeId, options = {}) => {
  if (!storeId) return;
  const { skipFetch = false, preserveState = false } = options;
  const storeChanged = storeId !== currentStoreId;

  currentStoreId = storeId;
  localStorage.setItem("selectedStoreId", currentStoreId);

  if (storeChanged && !preserveState) {
    operationStates.clear();
    hasUploaded = false;
    recentUploads = [];
    renderUploadProgress();
    if (fileTableBody) {
      fileTableBody.innerHTML =
        '<tr><td colspan="5" class="empty">Loading documents…</td></tr>';
    }
    setStep(1);
  }

  updateActiveStoreMeta();
  showWorkflow();
  renderModelList();

  if (!skipFetch) {
    await fetchFiles();
  }
};

const renderFiles = (files) => {
  renderUploadProgress();
  const operations = Array.from(operationStates.values());
  const processingOps = operations.filter((entry) => entry.status === "processing");
  const readyOps = operations.filter((entry) => entry.status === "success");
  const errorOps = operations.filter((entry) => entry.status === "error");

  fileTableBody.innerHTML = "";
  const documentCount = Array.isArray(files) ? files.length : 0;

  if (!files || documentCount === 0) {
    if (hasUploaded) {
      updateActiveStoreMeta(["Indexing in progress"]);
      if (processingOps.length) {
        fileTableBody.innerHTML = processingOps
          .map((entry) => `<tr><td colspan="5">${entry.friendlyName || entry.name} · indexing in progress…</td></tr>`)
          .join("");
      } else if (readyOps.length) {
        fileTableBody.innerHTML = readyOps
          .map((entry) => `<tr><td colspan="5">${entry.friendlyName || entry.name} · indexed (awaiting File Search listing)</td></tr>`)
          .join("");
      } else if (errorOps.length) {
        fileTableBody.innerHTML = errorOps
          .map((entry) => `<tr><td colspan="5">${entry.friendlyName || entry.name} · indexing failed: ${entry.error}</td></tr>`)
          .join("");
      } else if (recentUploads.length) {
        fileTableBody.innerHTML = recentUploads
          .map((name) => `<tr><td colspan="5">${name} · indexing in progress…</td></tr>`)
          .join("");
      } else {
        fileTableBody.innerHTML =
          '<tr><td colspan="5" class="empty">Upload complete. Google is still processing documents.</td></tr>';
      }
      setStep(Math.max(currentStep, readyOps.length ? 3 : 2));
    } else {
      updateActiveStoreMeta(["No documents yet"]);
      fileTableBody.innerHTML =
        '<tr><td colspan="5" class="empty">No documents yet. Upload to get started.</td></tr>';
      setStep(1);
    }
    return;
  }

  updateActiveStoreMeta([
    `${documentCount} document${documentCount === 1 ? "" : "s"}`,
  ]);

  const fileNames = new Set(files.map((file) => file.name || file.display_name));
  for (const [key, entry] of operationStates.entries()) {
    if (entry.status === "success") {
      const fileMatchName = entry.documentPath || entry.name || entry.friendlyName;
      if (
        (fileMatchName && fileNames.has(fileMatchName)) ||
        fileNames.has(entry.friendlyName || entry.name)
      ) {
        operationStates.delete(key);
      }
    }
  }
  renderUploadProgress();

  fileTableBody.innerHTML = files
    .map((file) => {
      const status = (file.state || "UNKNOWN").toUpperCase();
      let badgeClass = "processing";
      if (status === "READY") badgeClass = "ready";
      if (status === "FAILED") badgeClass = "failed";
      const chunks = file.chunk_count ?? "—";
      const updated = formatDate(file.update_time || file.create_time);
      const size = formatBytes(file.size_bytes);
      const name = file.display_name || file.name || "Document";

      return `
        <tr>
          <td>${name}</td>
          <td><span class="badge ${badgeClass}">${status}</span></td>
          <td>${chunks}</td>
          <td>${size}</td>
          <td>${updated}</td>
        </tr>
      `;
    })
    .join("");

  recentUploads = files.map(
    (file) =>
      file.display_name ||
      (file.name ? file.name.split("/").pop() : null) ||
      "document"
  );
  hasUploaded = true;
  setStep(3);
};

const fetchFiles = async () => {
  if (!currentStoreId) return;
  try {
    const url = `/files?store_id=${encodeURIComponent(currentStoreId)}`;
    const response = await fetch(url);
    if (!response.ok) throw new Error(await response.text());
    const payload = await response.json();
    renderFiles(payload.files || []);
    if ((payload.files || []).some((file) => (file.state || "").toUpperCase() === "READY")) {
      setStep(3);
    } else if (operationStates.size) {
      const hasProcessing = Array.from(operationStates.values()).some(
        (entry) => entry.status === "processing"
      );
      setStep(hasProcessing ? 2 : currentStep);
    } else {
      setStep(2);
    }
  } catch (error) {
    showToast(`Unable to load files: ${error.message}`, "error");
  }
};

const serializeOperation = (op) => {
  const name =
    op.display_name ||
    (op.document_name ? op.document_name.split("/").pop() : null) ||
    op.operation ||
    "document";
  return name;
};

const populateCitations = (container, citations = []) => {
  if (!container) return;
  container.innerHTML = "";
  if (!citations.length) return;

  citations.forEach((citation) => {
    const li = document.createElement("li");

    const titleText =
      citation.document_display_name || citation.title || citation.id || "Source";
    const linkTarget = citation.document_uri || citation.uri;
    const titleEl = document.createElement("div");
    titleEl.className = "citation-title";
    if (linkTarget) {
      const link = document.createElement("a");
      link.href = linkTarget;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = titleText;
      titleEl.appendChild(link);
    } else {
      titleEl.textContent = titleText;
    }
    li.appendChild(titleEl);

    const metaParts = [];
    if (citation.chunk_reference) {
      metaParts.push(citation.chunk_reference);
    }
    if (citation.document_path && citation.document_path !== citation.chunk_reference) {
      metaParts.push(citation.document_path);
    }
    if (metaParts.length) {
      const metaEl = document.createElement("div");
      metaEl.className = "citation-meta";
      metaEl.textContent = metaParts.join(" • ");
      li.appendChild(metaEl);
    }

    if (citation.snippet) {
      const snippet = document.createElement("div");
      snippet.textContent = citation.snippet;
      snippet.classList.add("snippet");
      li.appendChild(snippet);
    }

    if (citation.document_error) {
      const errorEl = document.createElement("div");
      errorEl.className = "citation-error";
      errorEl.textContent = `Metadata unavailable: ${citation.document_error}`;
      li.appendChild(errorEl);
    }

    container.appendChild(li);
  });
};

const addMessage = (role, content, citations = []) => {
  const clone = messageTemplate.content.cloneNode(true);
  const article = clone.querySelector(".message");
  article.dataset.role = role;

  const headerRole = clone.querySelector(".role");
  headerRole.textContent = role === "user" ? "You" : "Gemini";
  const timeEl = clone.querySelector("time");
  timeEl.textContent = new Date().toLocaleTimeString();

  const contentEl = clone.querySelector(".content");
  contentEl.textContent = content;

  const citationsList = clone.querySelector(".citations");
  populateCitations(citationsList, citations);

  chatThread.appendChild(clone);
  chatThread.scrollTop = chatThread.scrollHeight;
};

document.getElementById("file-upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = document.getElementById("file-input");
  if (!input.files || input.files.length === 0) {
    showToast("Select at least one file to upload.", "warning");
    return;
  }

  const selectedFiles = Array.from(input.files);
  renderSelectedFiles(selectedFiles);
  const formData = new FormData();
  selectedFiles.forEach((file) => {
    formData.append("files", file);
  });

  const button = event.target.querySelector("button");
  button.disabled = true;
  button.textContent = "Uploading…";
  updateUploadStatus(
    `Uploading ${selectedFiles.length} file${selectedFiles.length > 1 ? "s" : ""}…`,
    "active"
  );

  try {
    const url = currentStoreId ? `/upload?store_id=${encodeURIComponent(currentStoreId)}` : "/upload";
    const response = await fetch(url, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) throw new Error(await response.text());
    const payload = await response.json();
    const names = (payload.uploaded || []).map(serializeOperation);
    recentUploads = names;
    hasUploaded = true;
    const nameList = names.join(", ");
    updateUploadStatus(
      `Uploaded ${nameList || `${selectedFiles.length} file(s)`}. Indexing may take ~30-60 seconds.`,
      "success"
    );
    showToast(`Uploaded ${nameList || "files"} successfully.`, "success");
    (payload.uploaded || []).forEach((operation, idx) => {
      if (operation.operation) {
        const friendlyName = selectedFiles[idx]?.name || serializeOperation(operation);
        operationStates.set(operation.operation, {
          name: serializeOperation(operation),
          friendlyName,
          status: operation.done ? "success" : "processing",
          error: operation.error || null,
          documentPath: operation.document_name || null,
        });
        if (!operation.done) {
          scheduleOperationPoll(operation.operation);
        }
      }
    });
    renderUploadProgress();
    input.value = "";
    renderSelectedFiles([]);
    setStep(2);
    await fetchFiles();
  } catch (error) {
    showToast(`Upload failed: ${error.message}`, "error");
    updateUploadStatus(`Upload failed: ${error.message}`, "error");
  } finally {
    button.disabled = !(input.files && input.files.length);
    button.textContent = "Upload Selected Files";
  }
});

document.getElementById("url-upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const urlInput = document.getElementById("url-input");
  const displayInput = document.getElementById("url-display");

  const payload = {
    url: urlInput.value.trim(),
  };
  if (displayInput.value.trim()) {
    payload.display_name = displayInput.value.trim();
  }

  const button = event.target.querySelector("button");
  button.disabled = true;
  button.textContent = "Importing…";
  updateUploadStatus(`Importing ${payload.display_name || payload.url}…`, "active");

  try {
    const url = currentStoreId ? `/upload-url?store_id=${encodeURIComponent(currentStoreId)}` : "/upload-url";
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(await response.text());
    const body = await response.json();
    const name = serializeOperation((body.uploaded || [])[0] || {});
    recentUploads = [name];
    hasUploaded = true;
    showToast(`Imported ${name} successfully.`, "success");
    updateUploadStatus(
      `Imported ${name}. Google is chunking and embedding the document.`,
      "success"
    );
    urlInput.value = "";
    displayInput.value = "";
    setStep(2);
    await fetchFiles();
    (body.uploaded || []).forEach((operation) => {
      if (operation.operation) {
        const friendlyName = payload.display_name || operation.display_name || name;
        operationStates.set(operation.operation, {
          name: serializeOperation(operation),
          friendlyName,
          status: operation.done ? "success" : "processing",
          error: operation.error || null,
          documentPath: operation.document_name || null,
        });
        if (!operation.done) {
          scheduleOperationPoll(operation.operation);
        }
      }
    });
    renderUploadProgress();
  } catch (error) {
    showToast(`Import failed: ${error.message}`, "error");
    updateUploadStatus(`Import failed: ${error.message}`, "error");
  } finally {
    button.disabled = false;
    button.textContent = "Import From URL";
  }
});

document.getElementById("refresh-files").addEventListener("click", async () => {
  showToast("Refreshing documents…");
  await fetchFiles();
});

document.getElementById("file-input").addEventListener("change", (event) => {
  renderSelectedFiles(Array.from(event.target.files || []));
  const submitButton = document.querySelector("#file-upload-form button[type='submit']");
  if (submitButton) {
    submitButton.disabled = !(event.target.files && event.target.files.length);
  }
});

document.getElementById("chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = document.getElementById("chat-input");
  const maxChunks = parseInt(document.getElementById("chat-max-chunks").value, 10);
  const temperature = parseFloat(document.getElementById("chat-temperature").value);

  if (!input.value.trim()) {
    showToast("Enter a question to ask Gemini.", "warning");
    return;
  }

  const question = input.value.trim();
  addMessage("user", question);
  input.value = "";

  const thinkingId = (crypto?.randomUUID && crypto.randomUUID()) || String(Date.now());
  addMessage("assistant", "Thinking…", []);
  const placeholder = chatThread.lastElementChild;
  placeholder.dataset.id = thinkingId;

  try {
    const response = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        max_chunks: Number.isNaN(maxChunks) ? undefined : maxChunks,
        temperature: Number.isNaN(temperature) ? undefined : temperature,
        store_id: currentStoreId || undefined,
      }),
    });

    if (!response.ok) throw new Error(await response.text());
    const payload = await response.json();
    placeholder.querySelector(".content").textContent = payload.answer;
    const citationsList = placeholder.querySelector(".citations");
    populateCitations(citationsList, payload.citations || []);
    showToast("Answer ready with citations.", "success");
    setStep(3);
  } catch (error) {
    placeholder.remove();
    showToast(`Unable to complete request: ${error.message}`, "error");
  }
});

if (backToModelsBtn) {
  backToModelsBtn.addEventListener("click", () => {
    showModelHub();
    showToast("Select a model to continue.", "info");
  });
}

// Create model button event
createStoreBtn.addEventListener("click", () => {
  createStoreModal.classList.remove("hidden");
  storeNameInput.focus();
});

// Cancel store creation
cancelStoreBtn.addEventListener("click", () => {
  createStoreModal.classList.add("hidden");
  storeNameInput.value = "";
});

// Create store form submission
createStoreForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const storeName = storeNameInput.value.trim();

  if (!storeName) {
    showToast("Please enter a model name", "warning");
    return;
  }

  const submitBtn = createStoreForm.querySelector("button[type='submit']");
  submitBtn.disabled = true;
  submitBtn.textContent = "Creating...";

  try {
    await createStore(storeName);
    createStoreModal.classList.add("hidden");
    storeNameInput.value = "";

    // Reload files for the new model
    await fetchFiles();
  } catch (error) {
    // Error already shown in createStore
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Create Model";
  }
});

// Close modal on background click
createStoreModal.addEventListener("click", (event) => {
  if (event.target === createStoreModal) {
    createStoreModal.classList.add("hidden");
    storeNameInput.value = "";
  }
});

// Initialize
renderSelectedFiles([]);
setStep(1);
loadStores();


