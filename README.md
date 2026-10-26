# OpenCore Helper 3.0.1

Aplicativo para **Windows x64 e macOS Intel x64**, feito em **CustomTkinter**, que reúne o editor Auxiliary Tools, análise OHV, organização de EFI, backups, downloads oficiais e macOS Recovery

[![Windows build](https://github.com/Chimpi-hackintosh/OpenCore-Helper/actions/workflows/windows.yml/badge.svg)](https://github.com/Chimpi-hackintosh/OpenCore-Helper/actions/workflows/windows.yml)
[![MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

## Instalação

Baixe o instalador ou pacote portátil em [Releases](https://github.com/Chimpi-hackintosh/OpenCore-Helper/releases)

- `OpenCoreHelper-3.0.1-Setup-x64.exe`: instalação em Program Files, atalho no menu Iniciar e desinstalador
- `OpenCoreHelper-3.0.1-Windows-x64.zip`: extraia a pasta inteira e abra `OpenCoreHelper.exe`
- `SHA256SUMS.txt`: hashes dos pacotes publicados

O EXE inclui Python e suas dependências e não precisa de Python instalado no computador de destino

Os arquivos de uma versão aparecem após a conclusão do workflow **Windows build and release** — o workflow testa e compila o aplicativo antes de publicar a versão, preservando lançamentos já existentes

## macOS Intel x64

A distribuição macOS é preparada pelo workflow **OpenCore Helper - macOS x64** e fica disponível nos Artifacts da execução, sem publicar Releases automaticamente

O pacote inclui Python e Tcl/Tk e tem alvo mínimo macOS 10.15 Catalina. O build confere arquitetura e versões mínimas de todos os binários; os sistemas antigos ainda precisam de testes reais. Veja [compilação, compatibilidade e instalação no macOS](docs/MACOS.md)

## O que está implementado

| Área | Funcionalidades |
| --- | --- |
| Auxiliary Tools | Editor hierárquico de XML/binary plist, busca, filtro por seção, tipos, renomear, adicionar, excluir, reordenar arrays, desfazer e refazer |
| Proteção do documento | Salvamento atômico, cópia `.bak` antes de substituir um arquivo, detecção de alterações externas, preservação de chaves desconhecidas e do formato original |
| OpenCore | ACPI, Booter, DeviceProperties, Kernel, Misc, NVRAM, PlatformInfo e UEFI, incluindo estruturas de versões futuras |
| Snapshot | Inclusão de AML, kexts e drivers encontrados na pasta OC, sem apagar entradas existentes; novos kexts são ordenados pelas dependências disponíveis |
| SMBIOS | Edição de PlatformInfo/Generic, geração com macserial oficial configurado pelo usuário, UUID e ROM locais e exclusivos |
| Validação | Tipos, caminhos, arquivos ausentes, referências duplicadas e execução opcional do ocvalidate da mesma versão do OpenCore |
| EFI | Inspeção de cópias, backup ZIP com manifesto SHA-256, restauração verificada em pasta nova e área de trabalho a partir do OpenCorePkg oficial |
| OHV | Leitura de CPU, GPU, RAM, placa-mãe, BIOS, armazenamento, rede e áudio por CIM do Windows ou system_profiler/sysctl do macOS; análise preliminar com pendências explícitas |
| Downloads | Consulta à versão estável mais recente de OpenCorePkg, OCAT, Lilu, WhateverGreen, VirtualSMC, AppleALC e IntelMausi; conferência do digest quando fornecido pelo GitHub |
| Recovery | macrecovery oficial incluído, download de DMG e chunklist da Apple com verificação, cancelamento, hash de imagens e conversão opcional em VMDK pelo qemu-img |
| Relatórios | Exportação local em JSON, TXT e HTML com escaping de conteúdo |
| Interface | Português e inglês, idioma automático pelas preferências do Windows ou macOS, temas claro/escuro/sistema e tarefas demoradas fora da interface |

## Auxiliary Tools e o OCAT original

O editor integrado é uma implementação independente em CustomTkinter do editor do OpenCore Helper

O **[OpenCore Auxiliary Tools de ic005k](https://github.com/ic005k/OCAuxiliaryTools)** é um projeto separado em Qt e mantém sua autoria original. Para usá-lo junto do Helper, baixe seu ZIP oficial, extraia e selecione o EXE no Windows ou o aplicativo `.app` no macOS em **Configurações → Executável do OCAT oficial**. O botão **Abrir OCAT oficial** abre o arquivo salvo atual nesse aplicativo

O editor integrado não promete paridade com todos os recursos do OCAT original. Ele não migra automaticamente um config entre versões do OpenCore nem instala patches no sistema

## Começo rápido

1. Trabalhe em uma **cópia** da EFI
2. Abra `EFI/OC/config.plist` no Auxiliary Tools
3. Edite os valores ou use **Incluir arquivos EFI**, revise a ordem e salve
4. Para SMBIOS, configure o `macserial.exe` do OpenCorePkg em Configurações, selecione seu modelo e aplique os valores gerados
5. Execute **Analisar config** e o **ocvalidate correspondente à sua versão do OpenCore**
6. Crie um backup antes de usar a EFI em outro ambiente

Para começar do pacote oficial: baixe OpenCorePkg em Downloads e use **Área de EFI → Preparar área EFI**. O Sample.plist copiado precisa ser configurado para o hardware e não é uma EFI pronta para inicializar

## Recovery e VMware

Em **macOS Recovery**, informe Board ID e MLB e escolha uma pasta nova. Os valores padrão vêm do macrecovery original; a Apple decide a imagem retornada para aquele modelo. Não há promessa de uma versão específica a partir de um nome de preset

O download produz `BaseSystem.dmg` e `BaseSystem.chunklist`, não uma ISO nem um instalador offline completo. Para converter uma imagem já existente, configure `qemu-img.exe` em Configurações e use **Converter em VMDK**. Configure a VM e seu bootloader separadamente

O catálogo de versões e as instruções de recuperação são abertos nas fontes oficiais, sem uma lista interna de números de atualização que possa ficar desatualizada

## Executar pelo código

Requisitos de desenvolvimento: Windows x64 ou macOS Intel x64, Python 3.12 ou superior e Tcl/Tk incluído no Python. Para a distribuição macOS, use o Python oficial indicado em [MACOS.md](docs/MACOS.md)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

O launcher `Iniciar-OpenCore-Helper.cmd` usa esse ambiente. Para abrir um arquivo diretamente:

```powershell
.venv\Scripts\python main.py "D:\Minha EFI\EFI\OC\config.plist"
```

## Compilar EXE e instalador

Instale o NSIS no Windows e execute:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

Para gerar somente o pacote portátil, acrescente `--skip-installer`

O build usa PyInstaller em modo pasta, coleta recursos do CustomTkinter e separa `lib`, `locales`, licenças e defaults. A distribuição é verificada para impedir fontes `.py`/`.pyw` expostas. Isso não representa proteção contra engenharia reversa. Os executáveis não são assinados digitalmente

## Dados e preferências

- Instalação: `<Program Files x64>\SnoopyOS Company\OpenCore Helper`
- Dados por usuário: `<LocalAppData>\SnoopyOS Company\OpenCore Helper`
- `settings.json`, logs e estado editável ficam no perfil do usuário
- Atualizações e desinstalação preservam os dados por usuário
- O aplicativo não depende da pasta de trabalho e não precisa ser executado como administrador
- Nenhum relatório é transmitido automaticamente

O seletor de idioma tem prioridade sobre os idiomas de interface do Windows; na ausência de idioma suportado, o fallback é inglês. Português regional usa a tradução pt-BR

## Verificação

```powershell
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m ruff check main.py openhelper scripts tests --exclude openhelper/vendor
.venv\Scripts\python scripts\gui_smoke.py
```

O workflow verifica os testes em Linux e Windows, percorre as telas nos dois idiomas, compila o EXE, testa sua abertura fora da pasta de instalação e executa instalação, atualização e desinstalação em um runner Windows. Esses testes não validam inicialização de macOS nem todas as combinações de hardware

Consulte [arquitetura](docs/ARCHITECTURE.md), [migração da versão anterior](docs/MIGRATION.md), [notas 3.0.1](docs/releases/3.0.1.md) e [componentes de terceiros](THIRD_PARTY_NOTICES.md)

## Limites

OHV é uma análise preliminar e não oferece um percentual inventado de compatibilidade. A validação interna não substitui o esquema do OpenCore nem o ocvalidate. O aplicativo trabalha com arquivos e pastas escolhidos pelo usuário, sem montar, formatar ou gravar partições do sistema. As ferramentas externas são opcionais e só são executadas por ação do usuário

As distribuições são Windows x64 e macOS Intel x64. A variável `OCH_DEV_ALLOW_NON_WINDOWS=1` permite somente testes da interface em desenvolvimento no Linux; não é uma distribuição Linux

## English

OpenCore Helper 3.0.1 is an independent Windows x64 and macOS Intel x64 CustomTkinter application with a typed plist editor, EFI inspection and verified backups, preliminary hardware findings, upstream release downloads, SMBIOS editing through a user-selected macserial, Apple recovery downloads using bundled macrecovery, optional QEMU image conversion, and local reports

Download the setup or portable ZIP from Releases after the Windows build succeeds. The packaged application includes Python. The original Qt-based OCAT remains a separate project and can be launched through Settings. Match ocvalidate to your OpenCore release and review hardware-specific configuration before using any EFI

MIT license for original project code; see third-party notices for bundled components
