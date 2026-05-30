# Chaves RS256 — **somente desenvolvimento**

Este par de chaves RSA assina/valida os JWTs em **dev/CI**. É **intencionalmente
versionado** para que a aplicação, os testes e o container funcionem sem setup
manual e para que o JWKS seja estável entre restarts.

- `dev_private.pem` — chave privada (assina os tokens). **Nunca use em produção.**
- `dev_public.pem` — chave pública (valida os tokens; exposta via `/.well-known/jwks.json`).

## Produção

Em produção, **não** use estas chaves. Forneça um par próprio fora do repositório
apontando `RSA_PRIVATE_KEY_PATH` / `RSA_PUBLIC_KEY_PATH` para arquivos montados a
partir de um cofre de segredos (AWS Secrets Manager — ver US-23). A chave privada
de produção nunca deve ser commitada.

## Regenerar (dev)

```bash
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out dev_private.pem
openssl rsa -in dev_private.pem -pubout -out dev_public.pem
```
