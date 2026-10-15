# Monitor de precos (Hardware Barato -> Discord)

Todo dia de manha o GitHub Actions roda o `scraper.py`, pega o menor preco de cada
produto no Hardware Barato e posta um resumo no seu servidor do Discord.

## 1. Criar o webhook no Discord
1. No seu servidor, clique com o botao direito no canal > **Editar canal**.
2. **Integracoes** > **Webhooks** > **Novo webhook**.
3. De um nome (ex: "Precos") e clique em **Copiar URL do webhook**.

## 2. Testar no seu PC
```bash
python scraper.py --dry-run
```
Deve listar o menor preco e as primeiras ofertas de cada produto.
Se aparecer "nao consegui ler o preco", o site mudou o formato (veja o fim do arquivo).

Para testar o envio ao Discord (PowerShell):
```powershell
$env:DISCORD_WEBHOOK_URL="cole_a_url_aqui"; python scraper.py
```

## 3. Colocar no GitHub
1. Crie um repositorio **privado** e suba estes arquivos.
2. **Settings** > **Secrets and variables** > **Actions** > **New repository secret**
   - Nome: `DISCORD_WEBHOOK_URL`
   - Valor: a URL do webhook
3. Aba **Actions** > **Monitor de precos** > **Run workflow** para testar na hora.

Depois disso ele roda sozinho todo dia as 08:47 (horario de Brasilia).

## Adicionar ou mudar produtos
Edite o `products.json`. Pegue a URL do produto no hardwarebarato.com.br.
`target` e opcional: quando o preco ficar igual ou abaixo dele, a mensagem
marca `@here` e destaca o produto.

```json
{ "name": "Memoria 32GB DDR5 6000 CL30", "url": "https://www.hardwarebarato.com/...", "target": 1100 }
```

## Se parar de funcionar
O script procura nos links das ofertas o texto
`Ir para oferta na <Loja> por R$ <preco>`. Se o site mudar isso, ajuste a
expressao `OFFER_RE` no `scraper.py`.
