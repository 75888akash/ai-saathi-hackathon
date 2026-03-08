import json
import boto3
import base64
import hashlib
import logging
import re

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
polly = boto3.client('polly', region_name='ap-south-1')
s3 = boto3.client('s3', region_name='ap-south-1')

# Configuration
AUDIO_CACHE_BUCKET = 'ai-saathi-audio-cache'

# Voice mapping - Only Hindi and English
VOICE_MAP = {
    "hi": ("Aditi", "standard", "hi-IN"),
    "en": ("Joanna", "neural", "en-US")
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

def get_audio_cache_key(text, language):
    """Generate cache key for audio using same normalization as main Lambda"""
    normalized_text = normalize_query_for_cache(text)
    cache_input = f"{normalized_text}_{language}"
    return hashlib.md5(cache_input.encode()).hexdigest()

def get_cached_audio(cache_key):
    """Check if audio exists in S3 cache"""
    try:
        response = s3.get_object(Bucket=AUDIO_CACHE_BUCKET, Key=f"{cache_key}.mp3")
        audio_data = response['Body'].read()
        logger.info(f"✅ AUDIO CACHE HIT: {cache_key}")
        return base64.b64encode(audio_data).decode('utf-8')
    except s3.exceptions.NoSuchKey:
        logger.info(f"❌ AUDIO CACHE MISS: {cache_key}")
        return None
    except Exception as e:
        logger.warning(f"⚠️ S3 read error: {e}")
        return None

def store_audio_in_cache(cache_key, audio_data):
    """Store audio in S3 cache"""
    try:
        s3.put_object(
            Bucket=AUDIO_CACHE_BUCKET,
            Key=f"{cache_key}.mp3",
            Body=audio_data,
            ContentType='audio/mpeg'
        )
        logger.info(f"✅ AUDIO STORED IN S3: {cache_key}")
    except Exception as e:
        logger.warning(f"⚠️ S3 write error: {e}")

def generate_audio_with_polly(text, language):
    """Generate audio using Amazon Polly"""
    try:
        # Get voice configuration
        voice_id, engine, lang_code = VOICE_MAP.get(language, ("Aditi", "standard", "hi-IN"))
        
        # Truncate text if too long
        text = text[:3000] if len(text) > 3000 else text
        
        # Generate speech
        response = polly.synthesize_speech(
            Text=text,
            VoiceId=voice_id,
            OutputFormat='mp3',
            Engine=engine,
            LanguageCode=lang_code
        )
        
        audio_data = response['AudioStream'].read()
        logger.info(f"🎵 AUDIO GENERATED: {voice_id} ({language})")
        return audio_data
        
    except Exception as e:
        logger.error(f"❌ Polly error: {e}")
        return None

def lambda_handler(event, context):
    """Main Lambda handler for audio generation"""
    
    # Handle CORS preflight
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
        # Parse request
        body = json.loads(event.get("body", "{}"))
        text = body.get("text", "").strip()
        language = body.get("language", "hi").strip()
        
        # Validate input
        if not text or len(text) < 2:
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({"error": "Text is required"})
            }
        
        # Validate language (only Hindi and English supported)
        if language not in ["hi", "en"]:
            language = "hi"  # Default to Hindi
        
        logger.info(f"🎤 AUDIO REQUEST: {text[:50]}... (lang: {language})")
        
        # Generate cache key using same normalization as main Lambda
        cache_key = get_audio_cache_key(text, language)
        logger.info(f"🔑 AUDIO CACHE KEY: {cache_key}")
        
        # Check cache first
        cached_audio = get_cached_audio(cache_key)
        if cached_audio:
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({
                    "audio": cached_audio,
                    "cached": True
                })
            }
        
        # Generate new audio
        audio_data = generate_audio_with_polly(text, language)
        if not audio_data:
            return {
                "statusCode": 500,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({"error": "Audio generation failed"})
            }
        
        # Store in cache
        store_audio_in_cache(cache_key, audio_data)
        
        # Return base64 encoded audio
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "audio": audio_base64,
                "cached": False
            })
        }
        
    except Exception as e:
        logger.error(f"❌ Lambda error: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": "Internal server error"})
        }