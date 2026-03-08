# API Documentation - AI Saathi

## Base URL
```
https://jg30c7c6r7.execute-api.ap-south-1.amazonaws.com/prod
```

## Endpoints

### 1. Ask Question (Main API)

**Endpoint:** `POST /ask`

**Description:** Submit a question about government schemes and receive an AI-generated answer.

**Request Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "query": "प्रधानमंत्री आवास योजना क्या है?",
  "language": "hi"
}
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| query | string | Yes | User's question about government schemes |
| language | string | No | Language code: "hi" (Hindi) or "en" (English). Auto-detected if not provided |

**Response (Success - 200):**
```json
{
  "answer": "प्रधानमंत्री आवास योजना एक सरकारी योजना है...",
  "detected_language": "hi",
  "sources": ["scheme_document_1.pdf", "scheme_document_2.pdf"]
}
```

**Response Fields:**
| Field | Type | Description |
|-------|------|-------------|
| answer | string | AI-generated answer based on knowledge base |
| detected_language | string | Detected or specified language code |
| sources | array | List of source documents used for answer |

**Response (Error - 400):**
```json
{
  "answer": "कृपया सवाल पूछें।",
  "detected_language": "hi"
}
```

**Response (Error - 500):**
```json
{
  "error": "Error message"
}
```

**Example cURL:**
```bash
curl -X POST https://jg30c7c6r7.execute-api.ap-south-1.amazonaws.com/prod/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is Pradhan Mantri Awas Yojana?",
    "language": "en"
  }'
```

---

### 2. Generate Audio

**Endpoint:** `POST /audio`

**Description:** Convert text to speech using Amazon Polly.

**Request Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "text": "यह एक परीक्षण संदेश है",
  "language": "hi"
}
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| text | string | Yes | Text to convert to speech (max 3000 characters) |
| language | string | Yes | Language code: "hi" (Hindi) or "en" (English) |

**Response (Success - 200):**
```json
{
  "audio": "base64_encoded_mp3_data...",
  "cached": false
}
```

**Response Fields:**
| Field | Type | Description |
|-------|------|-------------|
| audio | string | Base64-encoded MP3 audio data |
| cached | boolean | Whether audio was retrieved from cache |

**Response (Error - 400):**
```json
{
  "error": "Text is required"
}
```

**Response (Error - 500):**
```json
{
  "error": "Audio generation failed"
}
```

**Example cURL:**
```bash
curl -X POST https://jg30c7c6r7.execute-api.ap-south-1.amazonaws.com/prod/audio \
  -H "Content-Type: application/json" \
  -d '{
    "text": "This is a test message",
    "language": "en"
  }'
```

**Playing Audio in Browser:**
```javascript
// Decode base64 and play
const audioData = response.audio;
const audioBlob = new Blob(
  [Uint8Array.from(atob(audioData), c => c.charCodeAt(0))],
  { type: 'audio/mpeg' }
);
const audioUrl = URL.createObjectURL(audioBlob);
const audio = new Audio(audioUrl);
audio.play();
```

---

## CORS Configuration

Both endpoints support CORS with the following headers:
```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: POST, OPTIONS
Access-Control-Allow-Headers: Content-Type
```

**OPTIONS Request:**
All endpoints support preflight OPTIONS requests for CORS.

---

## Rate Limits
- No explicit rate limits configured
- AWS Lambda concurrent execution limits apply
- Recommended: Implement client-side throttling

---

## Error Handling

### Common Error Codes
| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 400 | Bad Request (invalid input) |
| 500 | Internal Server Error |

### Error Response Format
```json
{
  "error": "Error description"
}
```

---

## Caching Behavior

### Answer Cache
- **Storage:** DynamoDB (ai-saathi-answer-cache)
- **TTL:** 7 days
- **Key:** MD5 hash of normalized query + language
- **Normalization:** Lowercase, punctuation removal, deduplication

### Audio Cache
- **Storage:** S3 (ai-saathi-audio-cache)
- **Key:** MD5 hash of normalized text + language
- **Format:** MP3
- **Voices:** 
  - Hindi: Aditi (standard)
  - English: Joanna (neural)

---

## Language Detection

If language is not specified in the request, the system automatically detects:
- **Hindi:** Presence of Devanagari characters (U+0900 to U+097F)
- **English:** Common English words
- **Default:** Hindi for ambiguous cases

---

## Query Validation

Queries are validated to reject:
- Empty or very short queries (< 2 characters)
- Repeated characters only
- Only numbers or special characters
- Common test patterns (e.g., "aaa bbb ccc")

Valid queries include broad questions like:
- "latest schemes"
- "government schemes"
- "प्रधानमंत्री योजनाएं"

---

## Knowledge Base Integration

### Retrieval Configuration
- **Knowledge Base ID:** 1VKMSXXJKH
- **Vector Search Results:** Top 5 documents
- **Model:** apac.amazon.nova-micro-v1:0
- **Max Tokens:** 500
- **Temperature:** 0.1

### Source Documents
- **Total:** 58 PDF documents
- **Storage:** S3 (ai-saathi-knowledge-docs)
- **Embeddings:** S3 (bedrock-knowledge-base-0xjz1f)

---

## Conversation Logging

All conversations are logged to DynamoDB:
- **Table:** ai-saathi-conversations
- **Fields:** conversation_id, timestamp, question, answer, language, sources
- **Purpose:** Analytics and improvement

---

## Best Practices

1. **Always specify language** for better performance
2. **Implement client-side caching** for repeated queries
3. **Handle audio playback errors** gracefully
4. **Validate input** before sending requests
5. **Use meaningful queries** for better results
6. **Implement retry logic** for failed requests

---

## Testing

### Test Cases

**1. Hindi Question:**
```bash
curl -X POST https://jg30c7c6r7.execute-api.ap-south-1.amazonaws.com/prod/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "आयुष्मान भारत योजना क्या है?", "language": "hi"}'
```

**2. English Question:**
```bash
curl -X POST https://jg30c7c6r7.execute-api.ap-south-1.amazonaws.com/prod/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "What is PM Kisan Yojana?", "language": "en"}'
```

**3. Auto Language Detection:**
```bash
curl -X POST https://jg30c7c6r7.execute-api.ap-south-1.amazonaws.com/prod/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "प्रधानमंत्री योजनाएं"}'
```

**4. Audio Generation:**
```bash
curl -X POST https://jg30c7c6r7.execute-api.ap-south-1.amazonaws.com/prod/audio \
  -H "Content-Type: application/json" \
  -d '{"text": "नमस्ते, यह एक परीक्षण है", "language": "hi"}'
```

---

## Support
For technical issues or questions, please refer to the main README or contact the developer.
