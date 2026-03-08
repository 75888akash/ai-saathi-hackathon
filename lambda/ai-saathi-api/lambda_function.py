import json
import boto3
import base64
import re
import hashlib
import time
from datetime import datetime
import uuid

bedrock_runtime = boto3.client("bedrock-runtime", region_name="ap-south-1")
bedrock_agent = boto3.client("bedrock-agent-runtime", region_name="ap-south-1")
polly = boto3.client("polly", region_name="ap-south-1")
dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")

# Tables
conversations_table = dynamodb.Table("ai-saathi-conversations")
cache_table = dynamodb.Table("ai-saathi-answer-cache")

# Configuration
KNOWLEDGE_BASE_ID = "1VKMSXXJKH"
CACHE_TTL_DAYS = 7

VOICE_MAP = {
    "hi": ("Aditi", "standard", "hi-IN"),
    "en": ("Joanna", "neural", "en-US")
}

LANG_NAMES = {
    "hi": "हिंदी",
    "en": "English"
}

def normalize_query_for_cache(query):
    """Light normalization for better cache hits while preserving meaning"""
    # Convert to lowercase
    normalized = query.lower().strip()
    
    # Remove punctuation (? , . ! etc.)
    normalized = re.sub(r'[^\w\s]', '', normalized)
    
    # Remove duplicate consecutive words (e.g., "any any" -> "any")
    words = normalized.split()
    deduplicated = []
    prev_word = None
    for word in words:
        if word != prev_word:
            deduplicated.append(word)
        prev_word = word
    
    # Join and normalize spaces
    normalized = ' '.join(deduplicated)
    
    # Normalize multiple spaces to single space
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized

def get_cache_key(query, language):
    normalized_query = normalize_query_for_cache(query)
    cache_input = f"{normalized_query}_{language}"
    return hashlib.md5(cache_input.encode()).hexdigest()

def get_from_cache(cache_key):
    try:
        response = cache_table.get_item(Key={'query_hash': cache_key})
        if 'Item' in response:
            item = response['Item']
            if item.get('ttl', 0) > int(time.time()):
                try:
                    cache_table.update_item(
                        Key={'query_hash': cache_key},
                        UpdateExpression='SET hit_count = if_not_exists(hit_count, :zero) + :inc',
                        ExpressionAttributeValues={':zero': 0, ':inc': 1}
                    )
                except:
                    pass
                print(f"✅ CACHE HIT: {cache_key} | Question: {item.get('question', 'N/A')}")
                return {
                    'answer': item.get('answer', ''),
                    'detected_language': item.get('language', 'hi'),
                    'sources': item.get('sources', [])
                }
            else:
                print(f"⏰ CACHE EXPIRED: {cache_key}")
        print(f"❌ CACHE MISS: {cache_key}")
        return None
    except Exception as e:
        print(f"⚠️ Cache read error: {e}")
        return None

def store_in_cache(cache_key, query, answer, language, sources):
    try:
        ttl = int(time.time()) + (CACHE_TTL_DAYS * 24 * 60 * 60)
        cache_table.put_item(
            Item={
                'query_hash': cache_key,
                'question': query,
                'answer': answer,
                'language': language,
                'sources': sources,
                'timestamp': int(time.time()),
                'ttl': ttl,
                'hit_count': 0
            },
            ConditionExpression='attribute_not_exists(query_hash)'
        )
        print(f"✅ STORED IN CACHE: {cache_key} | Question: {query}")
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        print(f"ℹ️ Cache entry already exists: {cache_key}")
    except Exception as e:
        print(f"⚠️ Cache write error: {e}")

def retrieve_from_knowledge_base(query):
    try:
        response = bedrock_agent.retrieve(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            retrievalQuery={'text': query},
            retrievalConfiguration={
                'vectorSearchConfiguration': {
                    'numberOfResults': 5
                }
            }
        )
        contexts = []
        sources = []
        for result in response.get('retrievalResults', []):
            contexts.append(result['content']['text'])
            source_uri = result.get('location', {}).get('s3Location', {}).get('uri', '')
            if source_uri:
                sources.append(source_uri.split('/')[-1])
        return {'context': '\n\n'.join(contexts), 'sources': list(set(sources))}
    except Exception as e:
        print(f"KB error: {e}")
        return {'context': '', 'sources': []}

def is_meaningful_question(query):
    """Improved validation - only reject truly meaningless queries"""
    query_lower = query.lower().strip()
    
    # Only reject if:
    # 1. Too short and not meaningful
    if len(query) < 2:
        return False
    
    # 2. Only repeated characters
    if len(set(query_lower.replace(' ', ''))) < 2:
        return False
    
    # 3. Only numbers or special characters
    if re.match(r'^[0-9\s\W]+$', query):
        return False
    
    # 4. Common test strings - be more strict
    test_patterns = [
        r'^(aaa|bbb|ccc|ddd|eee|fff|ggg|hhh|iii|jjj|kkk|lll|mmm|nnn|ooo|ppp|qqq|rrr|sss|ttt|uuu|vvv|www|xxx|yyy|zzz)\s*(aaa|bbb|ccc|ddd|eee|fff|ggg|hhh|iii|jjj|kkk|lll|mmm|nnn|ooo|ppp|qqq|rrr|sss|ttt|uuu|vvv|www|xxx|yyy|zzz)\s*(aaa|bbb|ccc|ddd|eee|fff|ggg|hhh|iii|jjj|kkk|lll|mmm|nnn|ooo|ppp|qqq|rrr|sss|ttt|uuu|vvv|www|xxx|yyy|zzz)\s*$',
        r'^(test|testing|check|checking)\s*(test|testing|check|checking)?\s*$',
        r'^(123|456|789|abc|xyz)\s*(123|456|789|abc|xyz)?\s*$',
        r'^[a-z]\s+[a-z]\s+[a-z]\s*$'  # Single letters with spaces
    ]
    
    for pattern in test_patterns:
        if re.match(pattern, query_lower):
            return False
    
    # Accept everything else including broad queries like "latest schemes"
    return True

def generate_answer(query, kb_context, language):
    context_text = kb_context.get('context', '')
    
    # Enhanced system prompt with better handling
    system_prompt = """You are AI Saathi, a government scheme information assistant for Indian citizens.

ROLE:
Provide accurate, structured, and easy-to-understand information about Indian government schemes.

STRICT RULES:
1. Never mention that you are an AI model.
2. Never mention Amazon, system creators, or internal technology.
3. Do not introduce yourself unless explicitly asked.
4. Do not generate internal codes, scheme codes, or metadata.
5. Do not include unrelated schemes when user asks about a specific scheme.

ANSWER FORMAT RULES:

1. If user asks about ONE specific scheme:
   - Start with a short natural paragraph explaining the scheme.
   - Then provide 3–5 key bullet points (Benefits, Eligibility, Amount, etc.).
   - Keep response concise and focused only on that scheme.

2. If user asks for MULTIPLE schemes or "list of schemes" or "latest schemes":
   - Provide a numbered list.
   - Each scheme should have 1–2 line description.
   - Do not over-explain.

3. If user asks about a specific detail (e.g., eligibility only):
   - Answer directly.
   - Do not repeat full scheme description.

4. Do not always use numbered format.
   Formatting must depend on the intent of the question.

5. NEVER reject broad queries like "latest schemes", "new schemes", "government schemes".
   Always provide helpful information even for broad questions.

6. If scheme doesn't exist or is discontinued:
   - Clearly state it's not available
   - Suggest similar active schemes if relevant

7. For regional/state-specific schemes:
   - Mention applicable states/regions
   - Direct to state government portals when needed

8. For "LATEST" or "NEW" scheme queries:
   - If you have recent scheme information, provide it
   - If not, clearly state the schemes are from available knowledge base
   - Never call old schemes "latest" - be honest about data currency

ENDING RULE:

IMPORTANT: Add ONLY ONE disclaimer at the end based on response language:
- English response → "For more information and the latest updates, please visit the official government website of the respective scheme."
- Hindi response → "अधिक जानकारी और नवीनतम अपडेट के लिए संबंधित योजना की आधिकारिक सरकारी वेबसाइट अवश्य देखें।"

NEVER include both disclaimers. NEVER mention this rule in your response.

Keep tone professional, neutral, and citizen-friendly.
Avoid robotic language."""
    
    if language == 'en':
        if context_text:
            prompt = f"Context:\n{context_text}\n\nQuestion: {query}\n\nProvide a helpful answer in English based on the context above. End with ONLY this disclaimer: 'For more information and the latest updates, please visit the official government website of the respective scheme.'"
        else:
            prompt = f"Question: {query}\n\nI don't have specific information about this in my knowledge base. Please ask about available government schemes or visit official government websites for the most current information. End with ONLY this disclaimer: 'For more information and the latest updates, please visit the official government website of the respective scheme.'"
    else:
        lang_name = LANG_NAMES.get(language, "हिंदी")
        if context_text:
            prompt = f"संदर्भ:\n{context_text}\n\nसवाल: {query}\n\nऊपर दिए गए संदर्भ के आधार पर {lang_name} में सहायक उत्तर दें। केवल इस अस्वीकरण के साथ समाप्त करें: 'अधिक जानकारी और नवीनतम अपडेट के लिए संबंधित योजना की आधिकारिक सरकारी वेबसाइट अवश्य देखें।'"
        else:
            prompt = f"सवाल: {query}\n\nमेरे पास इसकी विशिष्ट जानकारी नहीं है। कृपया उपलब्ध सरकारी योजनाओं के बारे में पूछें या नवीनतम जानकारी के लिए आधिकारिक सरकारी वेबसाइट देखें। केवल इस अस्वीकरण के साथ समाप्त करें: 'अधिक जानकारी और नवीनतम अपडेट के लिए संबंधित योजना की आधिकारिक सरकारी वेबसाइट अवश्य देखें।'"
    
    response = bedrock_runtime.invoke_model(
        modelId="apac.amazon.nova-micro-v1:0",
        body=json.dumps({
            "messages": [
                {"role": "user", "content": [{"text": f"{system_prompt}\n\n{prompt}"}]}
            ],
            "inferenceConfig": {"max_new_tokens": 500, "temperature": 0.1}
        })
    )
    result = json.loads(response["body"].read())
    return result["output"]["message"]["content"][0]["text"].strip()

def detect_language(text):
    # Check for Hindi/Devanagari characters
    if re.search(r'[\u0900-\u097F]', text):
        return "hi"
    
    # Check for English indicators
    english_words = ['the', 'and', 'or', 'is', 'are', 'was', 'were', 'have', 'has', 'will', 'would', 'can', 'could', 'should', 'may', 'might']
    text_lower = text.lower()
    if any(word in text_lower for word in english_words):
        return "en"
    
    # Default to Hindi for mixed/unclear cases
    return "hi"

def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            },
            "body": ""
        }
    
    try:
        body = json.loads(event.get("body", "{}"))
        # Accept both 'query' and 'question' for backward compatibility
        query = body.get("query", body.get("question", "")).strip()
        user_lang = body.get("language", "").strip()
        
        if not query:
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"answer": "कृपया सवाल पूछें।", "detected_language": "hi"})
            }
        
        # Improved validation - only reject truly meaningless queries
        if not is_meaningful_question(query):
            error_msg = "Please ask a meaningful question about government schemes." if user_lang == 'en' else "कृपया सरकारी योजनाओं के बारे में एक सार्थक सवाल पूछें।"
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"answer": error_msg, "detected_language": user_lang or "hi"})
            }

        detected_lang = user_lang if user_lang else detect_language(query)
        cache_key = get_cache_key(query, detected_lang)
        cached = get_from_cache(cache_key)
        
        if cached:
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps(cached)
            }
        
        print(f"🔍 QUERYING KNOWLEDGE BASE for: {query}")
        kb_context = retrieve_from_knowledge_base(query)
        print(f"📚 KB returned {len(kb_context.get('sources', []))} source documents")
        answer = generate_answer(query, kb_context, detected_lang)
        print(f"🤖 ANSWER GENERATED from Knowledge Base")
        sources = kb_context.get('sources', [])
        
        store_in_cache(cache_key, query, answer, detected_lang, sources)
        
        try:
            conversations_table.put_item(Item={
                "conversation_id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat(),
                "question": query,
                "answer": answer,
                "language": detected_lang,
                "sources": sources
            })
        except:
            pass

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({
                "answer": answer,
                "detected_language": detected_lang,
                "sources": sources
            })
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)})
        }