# Deploying RAG Maker to Vercel

This guide will help you deploy RAG Maker to Vercel for easy preview and testing.

## Prerequisites

1. A [Vercel account](https://vercel.com/signup) (free tier works fine)
2. [Vercel CLI](https://vercel.com/cli) installed: `npm install -g vercel`
3. A Google AI API key from [Google AI Studio](https://aistudio.google.com/apikey)

## Quick Deploy

### Option 1: Deploy via Vercel CLI

1. **Install Vercel CLI** (if not already installed):
   ```bash
   npm install -g vercel
   ```

2. **Login to Vercel**:
   ```bash
   vercel login
   ```

3. **Deploy from the project directory**:
   ```bash
   cd /home/user/RAG-Maker
   vercel
   ```

4. **Follow the prompts**:
   - Set up and deploy: `Y`
   - Which scope: Select your account
   - Link to existing project: `N`
   - Project name: `rag-maker` (or your preferred name)
   - Directory: `./` (current directory)
   - Override settings: `N`

5. **Set environment variables**:
   After deployment, add your API key:
   ```bash
   vercel env add GOOGLE_AI_API_KEY
   ```
   Paste your Google AI API key when prompted.

6. **Redeploy with environment variables**:
   ```bash
   vercel --prod
   ```

### Option 2: Deploy via Vercel Dashboard

1. **Push to GitHub** (if not already done):
   ```bash
   git push origin claude/ui-multiple-rags-016czpcKSnRtdvPkXQ8xDFY2
   ```

2. **Import to Vercel**:
   - Go to [vercel.com/new](https://vercel.com/new)
   - Import your GitHub repository
   - Configure project:
     - Framework Preset: Other
     - Root Directory: `./`
   - Add Environment Variable:
     - Name: `GOOGLE_AI_API_KEY`
     - Value: Your Google AI API key
   - Click "Deploy"

## Environment Variables

Required environment variables for Vercel:

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_AI_API_KEY` | Your Google AI API key | Yes |
| `GEMINI_MODEL` | Gemini model to use (default: models/gemini-1.5-flash-002) | No |
| `MAX_CHUNKS` | Maximum chunks for retrieval (default: 16) | No |
| `TEMPERATURE` | Model temperature (default: 0.3) | No |

## After Deployment

Once deployed, Vercel will provide you with a URL like:
- Production: `https://rag-maker.vercel.app`
- Preview: `https://rag-maker-xxx.vercel.app`

You can now:
1. Open the URL in your browser
2. See the multi-RAG store UI
3. Create stores, upload documents, and chat with your RAG system

## Troubleshooting

### Timeout Issues
Vercel has a 10-second timeout for serverless functions on the free tier. Large file uploads may timeout. For production use, consider:
- Upgrading to Vercel Pro
- Using a different deployment platform (Railway, Render, etc.)

### Module Import Errors
If you see import errors, ensure all dependencies are listed in `requirements.txt`.

### API Key Errors
Make sure you've set the `GOOGLE_AI_API_KEY` environment variable in Vercel's dashboard under:
`Project Settings → Environment Variables`

## Local Development

To run locally with the same setup:
```bash
vercel dev
```

This will start a local development server that mimics the Vercel environment.
