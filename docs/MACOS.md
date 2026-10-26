# OpenCore Helper para macOS Intel x64

O pacote é compilado como **x86_64**, com alvo mínimo **macOS 10.15 Catalina**.
Não é uma versão ARM64 nativa. A execução em Apple Silicon depende do Rosetta
e precisa de testes próprios. Não há promessa de compatibilidade com todos os
modelos de Mac, versões anteriores ao Catalina ou sistemas futuros.

## Compatibilidade e verificação

| Sistema Intel | Estado |
| --- | --- |
| macOS 10.15 Catalina, 11 Big Sur, 12 Monterey, 13 Ventura e 14 Sonoma | Alvos de compatibilidade; teste real em cada sistema ainda necessário |
| macOS 15 Sequoia | Build e abertura da interface verificados pelo workflow quando a execução passa |
| macOS 26 Tahoe | O mesmo pacote é aberto em um segundo runner Intel quando a execução passa |
| macOS 10.14 Mojave e anteriores | Fora do alvo desta distribuição |

O workflow usa Python 3.14.10 do python.org, cujo instalador declara suporte a
macOS 10.15 ou superior e inclui Tcl/Tk nativo. O instalador é conferido por
SHA-256 e assinatura antes da instalação no runner temporário.

O build verifica **todos os binários Mach-O** do pacote: arquitetura x86_64,
versão mínima de macOS de até 10.15 e assinatura ad hoc íntegra. A versão mínima
declarada em um binário não prova que todas as suas funções funcionem em todos
os sistemas antigos. O relatório `macos-build-report.json` registra essas
verificações e a versão do sistema do build.

## Compilar pelo GitHub

1. Abra a aba **Actions** do repositório
2. Selecione **OpenCore Helper - macOS x64**
3. Clique em **Run workflow** e escolha a branch que contém esta implementação
4. Aguarde os dois jobs terminarem com sucesso
5. Abra a execução e baixe **Artifacts → OpenCoreHelper-macOS-x64**
6. Extraia o ZIP do artifact e, depois, `OpenCoreHelper-3.0.1-macOS-x64.zip`

O pacote interno contém **OpenCore Helper.app**. Copie-o para **Aplicativos**.
O usuário final não precisa instalar Python nem CustomTkinter. A assinatura é
ad hoc, sem Developer ID e sem notarização. O Gatekeeper pode bloquear a
primeira abertura; use as opções normais de aprovação do macOS após conferir
a origem e o hash do download. O projeto não desativa o Gatekeeper.

## Recursos e dados

- Recursos, traduções, defaults e licenças: `OpenCore Helper.app/Contents/Resources`
- Preferências e logs: `~/Library/Application Support/SnoopyOS Company/OpenCore Helper`
- Idioma automático: ordem de `AppleLanguages`, com fallback para inglês
- Atalhos: **Command+O** para abrir e **Command+S** para salvar
- OHV: inventário local por `system_profiler` e `sysctl`, sem alterar o hardware

O inventário mantém somente campos selecionados dos dispositivos. Não inclui
os números de série, UUIDs, nomes de usuário ou endereços de rede retornados
pelo `system_profiler`. A análise continua sendo preliminar.

Selecione as versões **macOS** de `macserial`, `ocvalidate` e `qemu-img` em
Configurações. Para o OCAT original, selecione seu `.app` ou executável nativo.
Ferramentas `.exe` para Windows não são convertidas em programas macOS pelo build.

O editor plist, backups, downloads e Recovery usam a implementação comum do
Helper. Compilar o Helper não compila o bootloader OpenCore e não cria uma EFI
universal para todos os computadores. O aplicativo continua trabalhando apenas
em arquivos e pastas escolhidos pelo usuário.

## Compilar em um Mac Intel

Com Python 3.14.10 oficial e seus certificados instalados:

```bash
python3.14 -m venv .venv-macos
source .venv-macos/bin/activate
python -m pip install -r requirements-macos.txt
python -m pytest -q
python scripts/gui_smoke.py
python scripts/build_macos.py
```

Saída: `dist/OpenCoreHelper-3.0.1-macOS-x64.zip`, hash SHA-256 e relatório do build.
O ZIP é criado com `ditto` para preservar permissões e links simbólicos do `.app`.
O workflow disponibiliza artifacts; ele não publica Releases automaticamente.

Fontes técnicas:
- https://www.python.org/downloads/release/python-31410/
- https://docs.python.org/3.14/using/mac.html
- https://pyinstaller.org/en/stable/feature-notes.html#macos-multi-arch-support
