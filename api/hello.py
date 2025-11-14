def handler(event, context):
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'text/plain'},
        'body': 'Hello from Vercel Python! If you see this, Python functions work.'
    }
