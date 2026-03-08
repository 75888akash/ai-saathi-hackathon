# Deployment Guide - AI Saathi

## Prerequisites

### AWS Account Requirements
- Active AWS Account
- IAM permissions for:
  - Lambda (create, update, invoke)
  - S3 (create buckets, upload files)
  - DynamoDB (create tables)
  - API Gateway (create APIs)
  - CloudFront (create distributions)
  - Bedrock (access to models and knowledge bases)
  - Polly (synthesize speech)

### Tools Required
- AWS CLI (configured with credentials)
- Python 3.12
- Git
- Text editor

### AWS Region
All resources are deployed in: **ap-south-1** (Mumbai)

---

## Step 1: S3 Buckets Setup

### Create S3 Buckets
```bash
# Knowledge base documents
aws s3 mb s3://ai-saathi-knowledge-docs --region ap-south-1

# Vector embeddings
aws s3 mb s3://bedrock-knowledge-base-0xjz1f --region ap-south-1

# Audio cache
aws s3 mb s3://ai-saathi-audio-cache --region ap-south-1

# Frontend - Main chat
aws s3 mb s3://ai-saathi-web-akash --region ap-south-1

# Frontend - Demo portal
aws s3 mb s3://ai-saathi-demo-portal --region ap-south-1
```

### Configure S3 for Static Website Hosting
```bash
# Main chat
aws s3 website s3://ai-saathi-web-akash \
  --index-document index.html \
  --region ap-south-1

# Demo portal
aws s3 website s3://ai-saathi-demo-portal \
  --index-document index.html \
  --region ap-south-1
```

### Upload Frontend Files
```bash
# Main chat
aws s3 sync frontend/main-chat/ s3://ai-saathi-web-akash/ --region ap-south-1

# Demo portal
aws s3 sync frontend/demo-portal/ s3://ai-saathi-demo-portal/ --region ap-south-1
```

### Set Bucket Policies (Public Read)
```bash
# Create policy file: bucket-policy.json
cat > bucket-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::BUCKET_NAME/*"
    }
  ]
}
EOF

# Apply to buckets (replace BUCKET_NAME)
aws s3api put-bucket-policy --bucket ai-saathi-web-akash --policy file://bucket-policy.json
aws s3api put-bucket-policy --bucket ai-saathi-demo-portal --policy file://bucket-policy.json
```

---

## Step 2: DynamoDB Tables Setup

### Create Answer Cache Table
```bash
aws dynamodb create-table \
  --table-name ai-saathi-answer-cache \
  --attribute-definitions \
    AttributeName=query_hash,AttributeType=S \
  --key-schema \
    AttributeName=query_hash,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region ap-south-1
```

### Create Conversations Table
```bash
aws dynamodb create-table \
  --table-name ai-saathi-conversations \
  --attribute-definitions \
    AttributeName=conversation_id,AttributeType=S \
  --key-schema \
    AttributeName=conversation_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region ap-south-1
```

### Enable TTL on Cache Table
```bash
aws dynamodb update-time-to-live \
  --table-name ai-saathi-answer-cache \
  --time-to-live-specification "Enabled=true, AttributeName=ttl" \
  --region ap-south-1
```

---

## Step 3: Amazon Bedrock Knowledge Base Setup

### 1. Upload Knowledge Base Documents
```bash
# Upload your PDF documents to S3
aws s3 sync /path/to/your/pdfs/ s3://ai-saathi-knowledge-docs/ --region ap-south-1
```

### 2. Create Knowledge Base (via AWS Console)
1. Go to Amazon Bedrock Console
2. Navigate to Knowledge Bases
3. Click "Create knowledge base"
4. Configure:
   - Name: ai-saathi-kb
   - Data source: S3 (ai-saathi-knowledge-docs)
   - Embeddings model: Titan Embeddings G1 - Text
   - Vector store: S3 (bedrock-knowledge-base-0xjz1f)
5. Note the Knowledge Base ID: **1VKMSXXJKH**

### 3. Sync Knowledge Base
```bash
# Trigger sync via console or CLI
aws bedrock-agent start-ingestion-job \
  --knowledge-base-id 1VKMSXXJKH \
  --data-source-id <DATA_SOURCE_ID> \
  --region ap-south-1
```

---

## Step 4: IAM Role for Lambda

### Create Lambda Execution Role
```bash
# Create trust policy
cat > lambda-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name ai-saathi-lambda-role \
  --assume-role-policy-document file://lambda-trust-policy.json
```

### Attach Policies
```bash
# Basic Lambda execution
aws iam attach-role-policy \
  --role-name ai-saathi-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# DynamoDB access
aws iam attach-role-policy \
  --role-name ai-saathi-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess

# S3 access
aws iam attach-role-policy \
  --role-name ai-saathi-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

# Bedrock access
aws iam attach-role-policy \
  --role-name ai-saathi-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess

# Polly access
aws iam attach-role-policy \
  --role-name ai-saathi-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonPollyFullAccess
```

---

## Step 5: Deploy Lambda Functions

### Package and Deploy ai-saathi-api
```bash
cd lambda/ai-saathi-api

# Create deployment package
zip -r function.zip lambda_function.py

# Create Lambda function
aws lambda create-function \
  --function-name ai-saathi-api \
  --runtime python3.12 \
  --role arn:aws:iam::ACCOUNT_ID:role/ai-saathi-lambda-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 30 \
  --memory-size 256 \
  --region ap-south-1
```

### Package and Deploy ai-saathi-audio
```bash
cd ../ai-saathi-audio

# Create deployment package
zip -r function.zip lambda_function.py

# Create Lambda function
aws lambda create-function \
  --function-name ai-saathi-audio \
  --runtime python3.12 \
  --role arn:aws:iam::ACCOUNT_ID:role/ai-saathi-lambda-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 30 \
  --memory-size 512 \
  --region ap-south-1
```

---

## Step 6: API Gateway Setup

### Create HTTP API
```bash
aws apigatewayv2 create-api \
  --name ai-saathi-api \
  --protocol-type HTTP \
  --cors-configuration AllowOrigins="*",AllowMethods="POST,OPTIONS",AllowHeaders="Content-Type" \
  --region ap-south-1
```

### Create Lambda Integrations
```bash
# Get API ID from previous command output
API_ID=jg30c7c6r7

# Create integration for /ask
aws apigatewayv2 create-integration \
  --api-id $API_ID \
  --integration-type AWS_PROXY \
  --integration-uri arn:aws:lambda:ap-south-1:ACCOUNT_ID:function:ai-saathi-api \
  --payload-format-version 2.0 \
  --region ap-south-1

# Create integration for /audio
aws apigatewayv2 create-integration \
  --api-id $API_ID \
  --integration-type AWS_PROXY \
  --integration-uri arn:aws:lambda:ap-south-1:ACCOUNT_ID:function:ai-saathi-audio \
  --payload-format-version 2.0 \
  --region ap-south-1
```

### Create Routes
```bash
# Create /ask route
aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "POST /ask" \
  --target integrations/INTEGRATION_ID \
  --region ap-south-1

# Create /audio route
aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "POST /audio" \
  --target integrations/INTEGRATION_ID \
  --region ap-south-1
```

### Create Stage
```bash
aws apigatewayv2 create-stage \
  --api-id $API_ID \
  --stage-name prod \
  --auto-deploy \
  --region ap-south-1
```

### Grant API Gateway Permission to Invoke Lambda
```bash
# For ai-saathi-api
aws lambda add-permission \
  --function-name ai-saathi-api \
  --statement-id apigateway-invoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:ap-south-1:ACCOUNT_ID:$API_ID/*/*" \
  --region ap-south-1

# For ai-saathi-audio
aws lambda add-permission \
  --function-name ai-saathi-audio \
  --statement-id apigateway-invoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:ap-south-1:ACCOUNT_ID:$API_ID/*/*" \
  --region ap-south-1
```

---

## Step 7: CloudFront Setup

### Create CloudFront Distribution for Main Chat
```bash
# Via AWS Console:
1. Go to CloudFront
2. Create Distribution
3. Origin: ai-saathi-web-akash.s3-website.ap-south-1.amazonaws.com
4. Default cache behavior: Allow GET, HEAD
5. Alternate domain: ai-saathi.techietech.shop
6. SSL Certificate: Request/Import certificate
7. Create distribution
8. Note Distribution ID: EPBY76Z26CA8D
```

### Create CloudFront Distribution for Demo Portal
```bash
# Via AWS Console:
1. Create Distribution
2. Origin: ai-saathi-demo-portal.s3-website.ap-south-1.amazonaws.com
3. Alternate domain: demo.techietech.shop
4. Note Distribution ID: EWR0A4PSPJ32G
```

---

## Step 8: DNS Configuration

### Update DNS Records (Route 53 or your DNS provider)
```
Type: CNAME
Name: ai-saathi.techietech.shop
Value: <CloudFront Distribution Domain>

Type: CNAME
Name: demo.techietech.shop
Value: <CloudFront Distribution Domain>
```

---

## Step 9: Update Frontend Configuration

### Update API Endpoint in Frontend Files
Edit `frontend/main-chat/index.html` and `frontend/demo-portal/chatbot.js`:
```javascript
const API_ENDPOINT = 'https://jg30c7c6r7.execute-api.ap-south-1.amazonaws.com/prod';
```

### Re-upload Frontend Files
```bash
aws s3 sync frontend/main-chat/ s3://ai-saathi-web-akash/ --region ap-south-1
aws s3 sync frontend/demo-portal/ s3://ai-saathi-demo-portal/ --region ap-south-1
```

### Invalidate CloudFront Cache
```bash
aws cloudfront create-invalidation \
  --distribution-id EPBY76Z26CA8D \
  --paths "/*"

aws cloudfront create-invalidation \
  --distribution-id EWR0A4PSPJ32G \
  --paths "/*"
```

---

## Step 10: Testing

### Test Lambda Functions
```bash
# Test ai-saathi-api
aws lambda invoke \
  --function-name ai-saathi-api \
  --payload '{"body": "{\"query\": \"test\", \"language\": \"hi\"}"}' \
  --region ap-south-1 \
  response.json

# Test ai-saathi-audio
aws lambda invoke \
  --function-name ai-saathi-audio \
  --payload '{"body": "{\"text\": \"test\", \"language\": \"hi\"}"}' \
  --region ap-south-1 \
  response.json
```

### Test API Gateway
```bash
curl -X POST https://jg30c7c6r7.execute-api.ap-south-1.amazonaws.com/prod/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "language": "hi"}'
```

### Test Frontend
Open browser and navigate to:
- https://ai-saathi.techietech.shop
- https://demo.techietech.shop

---

## Monitoring and Logs

### CloudWatch Logs
```bash
# View Lambda logs
aws logs tail /aws/lambda/ai-saathi-api --follow --region ap-south-1
aws logs tail /aws/lambda/ai-saathi-audio --follow --region ap-south-1
```

### DynamoDB Metrics
```bash
# Check table metrics in AWS Console
# Monitor: Read/Write capacity, Item count, Storage size
```

---

## Cost Optimization

1. **Use DynamoDB On-Demand** for unpredictable traffic
2. **Enable S3 Lifecycle Policies** for audio cache
3. **Set CloudWatch Log Retention** to 7-30 days
4. **Monitor Lambda Concurrent Executions**
5. **Use CloudFront Caching** effectively

---

## Troubleshooting

### Common Issues

**1. Lambda Timeout**
- Increase timeout in Lambda configuration
- Check Bedrock Knowledge Base response time

**2. CORS Errors**
- Verify API Gateway CORS configuration
- Check Lambda response headers

**3. Cache Not Working**
- Verify DynamoDB table exists
- Check IAM permissions
- Review CloudWatch logs

**4. Audio Not Playing**
- Check S3 bucket permissions
- Verify Polly voice availability in region
- Test base64 decoding

---

## Security Hardening (Production)

1. **Enable AWS WAF** on API Gateway
2. **Implement API Keys** or Cognito authentication
3. **Restrict S3 bucket access** to CloudFront only
4. **Enable CloudTrail** for audit logging
5. **Use Secrets Manager** for sensitive configuration
6. **Implement rate limiting** on API Gateway
7. **Enable VPC** for Lambda functions

---

## Backup and Disaster Recovery

### Backup Strategy
```bash
# DynamoDB backups
aws dynamodb create-backup \
  --table-name ai-saathi-answer-cache \
  --backup-name ai-saathi-cache-backup-$(date +%Y%m%d)

# S3 versioning
aws s3api put-bucket-versioning \
  --bucket ai-saathi-knowledge-docs \
  --versioning-configuration Status=Enabled
```

---

## Support
For deployment issues, refer to AWS documentation or contact the developer.
