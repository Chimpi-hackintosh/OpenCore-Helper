# Aviso de suporte e atualizações

## Política

A partir de **04/11/2026 às 00h UTC**, versões abaixo da mínima declarada deixam de receber correções de segurança do proprietário

Antes dessa data o aviso informa que o suporte está prestes a terminar — depois informa que as atualizações de segurança terminaram

O texto explica o risco de falhas sem afirmar que o usuário ou o aplicativo já foi infectado

| Aplicativo | Versão publicada conferida em 02/11/2026 | Mínima |
| --- | --- | --- |
| OpenCore Helper | v3.0.2 | 3.0.2 |

## Comportamento

- Detecta o idioma do sistema ou navegador — português, inglês, espanhol, francês, alemão, italiano, russo, chinês, japonês, coreano, árabe e hindi, com inglês como alternativa
- Compara versões numericamente e ignora sufixos de build quando o aplicativo só informa a série de versão
- Consulta somente dados públicos de suporte por HTTPS, com prazo limitado e catálogo local quando está sem internet
- Não envia arquivos, prompts, senhas, dados de hardware ou dados NFC
- Antes do corte, o aviso mostra a versão instalada e a mínima e pode ser adiado
- Depois do corte, ao abrir ou reabrir uma instalação registrada no Windows 11 x64 nativo, o aviso pede a atualização se o catálogo e o GitHub confirmarem o mesmo instalador estável e houver espaço para prepará-lo
- A atualização baixa e confere o SHA-256 do instalador, usa a confirmação de fechamento do editor e abre o instalador normal do Windows, com as permissões exigidas pelo próprio instalador
- Se a versão antiga ainda abrir após uma tentativa, a orientação de reinstalação só aparece com o pacote local novamente conferido e os pré-requisitos locais ainda válidos. O usuário precisa confirmar que a tentativa terminou, verificar os requisitos do instalador e guardar cópias dos dados antes de desinstalar manualmente
- Se o pacote não puder ser verificado ou preparado, o aviso oferece a página oficial. Instalações portáteis, Windows fora da faixa da atualização assistida e macOS continuam com o aviso informativo
- A atualização não solicita reinício do computador. Depois de concluir o instalador, reabra o aplicativo para conferir a versão

A tabela pública fica em [Apps e suporte](https://chimpi-hackintosh.github.io/ChimpiBlender-Online/support.html) depois que o PR do site for integrado e o Pages for publicado

## Distribuição e limites

**Alterar o repositório não altera binários já instalados** — versões antigas sem verificador precisam receber uma atualização manual inicial para passarem a consultar a política

Este PR entrega código e verificações — não equivale a um novo Release, atualização instalada ou site já implantado

As prévias continuam identificadas como prévias — os números da tabela vêm de lançamentos existentes e não foram inventados para esta alteração

O catálogo público não inclui repositórios privados

## Validação local desta alteração

`python -m pytest -q`: 72 testes aprovados

`ruff check main.py openhelper scripts tests --exclude openhelper/vendor`: aprovado

Os testes do aviso cobrem versões iguais e mais novas sem alerta, versões antigas com alerta, mudança exata de data, traduções, falha de rede e rejeição de links não oficiais

`CHIMPI_SUPPORT_CHECK=0` desliga a consulta opcional — os modos de smoke test também evitam rede e avisos durante a compilação
