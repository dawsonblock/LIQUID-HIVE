# Production-Grade Secrets Management

LIQUID-HIVE implements a comprehensive secrets management system that supports multiple providers with intelligent fallback mechanisms, ensuring secure operation across development, staging, and production environments.

## Architecture Overview

The secrets management system follows a priority-based approach:

1. **HashiCorp Vault** (Primary for local development)
2. **AWS Secrets Manager** (Primary for production)
3. **Environment Variables** (Fallback)

## Supported Providers

### 1. HashiCorp Vault

**Use Case**: Local development, on-premises deployments
**Features**: 
- KV v1 and v2 secret engines
- Token-based authentication
- Development mode for local testing
- Production-ready clustering support

**Configuration**:
```yaml
secrets:
  provider: "vault"
  vault:
    enabled: true
    address: "http://vault:8200"
    token: "your-vault-token"
    mountPath: "secret"
```

### 2. AWS Secrets Manager

**Use Case**: Production deployments on AWS
**Features**:
- Native AWS integration
- Automatic rotation support
- IAM-based access control
- JSON and string secret formats

**Configuration**:
```yaml
secrets:
  provider: "aws-secrets-manager"
  aws:
    enabled: true
    region: "us-east-1"
    secretsPrefix: "liquid-hive/prod"
    serviceAccount:
      create: true
      annotations:
        eks.amazonaws.com/role-arn: "arn:aws:iam::123456789012:role/liquid-hive-secrets-role"
```

### 3. Environment Variables

**Use Case**: Fallback, simple deployments
**Features**:
- Direct environment variable access
- Compatible with existing configurations
- No external dependencies

## Quick Start

### Local Development with Vault

1. **Deploy with development Vault**:
```bash
helm install liquid-hive ./helm/liquid-hive -f ./helm/liquid-hive/values-dev.yaml
```

2. **Store secrets in Vault**:
```bash
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=dev-token

# Store database connection
vault kv put secret/database/mongo_url value="mongodb://mongo:27017/liquid-hive"

# Store AI endpoints  
vault kv put secret/ai/vllm_endpoint value="http://vllm:8000"
vault kv put secret/ai/vllm_api_key value="your-api-key"

# Store monitoring config
vault kv put secret/monitoring/prometheus_base_url value="http://prometheus:9090"
```

### AWS Production Deployment

1. **Create IAM Role for Service Account**:
```bash
# Create IAM policy
cat > liquid-hive-secrets-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue",
                "secretsmanager:DescribeSecret"
            ],
            "Resource": "arn:aws:secretsmanager:*:*:secret:liquid-hive/*"
        }
    ]
}
EOF

aws iam create-policy \
    --policy-name LiquidHiveSecretsPolicy \
    --policy-document file://liquid-hive-secrets-policy.json

# Create IAM role for service account (requires OIDC provider)
eksctl create iamserviceaccount \
    --cluster your-cluster-name \
    --namespace default \
    --name liquid-hive-secrets \
    --attach-policy-arn arn:aws:iam::123456789012:policy/LiquidHiveSecretsPolicy \
    --approve
```

2. **Store secrets in AWS Secrets Manager**:
```bash
# Database connection
aws secretsmanager create-secret \
    --name "liquid-hive/prod/database/mongo_url" \
    --secret-string "mongodb://prod-mongo:27017/liquid-hive"

# Redis connection
aws secretsmanager create-secret \
    --name "liquid-hive/prod/database/redis_url" \
    --secret-string "redis://prod-redis:6379"

# AI configuration
aws secretsmanager create-secret \
    --name "liquid-hive/prod/ai/vllm_endpoint" \
    --secret-string "http://vllm-large:8000"

aws secretsmanager create-secret \
    --name "liquid-hive/prod/ai/vllm_api_key" \
    --secret-string "your-production-api-key"
```

3. **Deploy to production**:
```bash
helm install liquid-hive ./helm/liquid-hive -f ./helm/liquid-hive/values-aws-prod.yaml
```

## Secret Naming Conventions

### Vault Paths
```
secret/
├── database/
│   ├── mongo_url
│   ├── redis_url
│   └── neo4j_url
├── ai/
│   ├── vllm_endpoint
│   ├── vllm_endpoint_small
│   ├── vllm_endpoint_large
│   └── vllm_api_key
└── monitoring/
    └── prometheus_base_url
```

### AWS Secrets Manager Names
```
liquid-hive/prod/
├── database/mongo_url
├── database/redis_url
├── database/neo4j_url
├── ai/vllm_endpoint
├── ai/vllm_endpoint_small
├── ai/vllm_endpoint_large
├── ai/vllm_api_key
└── monitoring/prometheus_base_url
```

### Environment Variables (Fallback)
```
MONGO_URL
REDIS_URL
NEO4J_URL
VLLM_ENDPOINT
VLLM_ENDPOINT_SMALL
VLLM_ENDPOINT_LARGE
VLLM_API_KEY
PROMETHEUS_BASE_URL
```

## API Endpoints

### Health Check
```bash
curl http://localhost:8080/secrets/health
```

**Response**:
```json
{
  "active_provider": "vault",
  "providers": {
    "vault": {
      "status": "healthy",
      "authenticated": true
    },
    "aws_secrets_manager": {
      "status": "not_configured"
    },
    "environment": {
      "status": "healthy"
    }
  }
}
```

### Application Configuration
The secrets manager automatically loads configuration during application startup. No manual intervention required for standard operations.

## Security Best Practices

### Development Environment
- Use development Vault with in-memory storage
- Rotate development tokens regularly
- Never commit secrets to version control
- Use separate secret paths for each environment

### Production Environment
- Use IAM roles for service accounts (no hardcoded credentials)
- Enable secret rotation where supported
- Implement least privilege access policies
- Monitor secret access logs
- Use separate AWS accounts for different environments

### Network Security
- Restrict Vault access to authorized networks
- Use TLS encryption for all communications
- Implement proper firewall rules
- Consider using AWS PrivateLink for Secrets Manager access

## Troubleshooting

### Common Issues

1. **Vault Connection Failed**
```bash
# Check Vault status
kubectl exec -it vault-pod -- vault status

# Check authentication
kubectl logs deployment/liquid-hive | grep vault
```

2. **AWS Secrets Manager Access Denied**
```bash
# Check service account annotations
kubectl describe sa liquid-hive-secrets

# Check IAM role permissions
aws sts get-caller-identity
aws secretsmanager list-secrets --max-items 1
```

3. **Fallback to Environment Variables**
```bash
# Check configuration loading
kubectl logs deployment/liquid-hive | grep "secrets provider"

# Verify environment variables
kubectl exec -it liquid-hive-pod -- printenv | grep -E "(MONGO_URL|REDIS_URL|VLLM_ENDPOINT)"
```

### Debug Mode
Enable debug logging for secrets manager:
```yaml
env:
- name: LOG_LEVEL
  value: "DEBUG"
```

## Migration Guide

### From Environment Variables to Vault
1. Export current environment variables
2. Store them in Vault using the naming conventions above
3. Update deployment configuration to use Vault provider
4. Verify health endpoint shows Vault as active provider

### From Vault to AWS Secrets Manager
1. Extract secrets from Vault
2. Create equivalent secrets in AWS Secrets Manager
3. Update deployment configuration for AWS provider
4. Verify health endpoint shows AWS as active provider

## Performance Considerations

- **Caching**: Secrets are cached in memory after first retrieval
- **Startup Time**: Initial secret loading may add 2-5 seconds to startup
- **Network Latency**: Consider deploying Vault close to application for optimal performance
- **Rate Limits**: AWS Secrets Manager has API rate limits (5000 calls/second)

## Monitoring and Alerting

### Key Metrics to Monitor
- Secret retrieval success/failure rates
- Authentication status for each provider  
- Cache hit rates
- Network latency to secret stores

### Recommended Alerts
- Secrets manager authentication failures
- High secret retrieval error rates
- Vault seal status changes
- AWS IAM permission denials

## Backup and Recovery

### Vault Backup
```bash
# Export secrets for backup
vault kv export secret/ > vault-backup.json
```

### AWS Secrets Manager Recovery
AWS Secrets Manager provides automatic backup and point-in-time recovery. Configure retention policies based on compliance requirements.

## Compliance and Auditing

- All secret access is logged through application logs
- Vault provides detailed audit logging capabilities
- AWS CloudTrail records all Secrets Manager API calls
- Regular secret rotation schedules should be established
- Access reviews should be conducted quarterly

## Support and Contributing

For issues related to secrets management:
1. Check the health endpoint first
2. Review application logs for secret loading errors
3. Verify network connectivity to secret stores
4. Validate IAM permissions (for AWS) or token validity (for Vault)

For feature requests or bug reports, please see our contributing guidelines.