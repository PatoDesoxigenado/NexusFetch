# 🔻 Nexus Fetch

Um aplicativo desktop moderno, rápido e sem complicações para baixar mídias de diversas plataformas (YouTube, Twitter/X e Instagram). Com uma interface limpa desenvolvida em **CustomTkinter** (tema escuro de alto contraste em Vermelho, Preto e Branco), você pode baixar vídeos, áudios (MP3), animações (.GIF), imagens e playlists completas em resolução máxima, sem precisar lidar com linhas de comando.

---

## ✨ Funcionalidades Principais

- **Interface Moderna e Fluida (CustomTkinter):**
  - Paleta de cores exclusiva (Vermelho Nexus `#E50914`, Preto profundo `#0D0E11` e Branco).
  - Cantos arredondados, animações de *hover* e layout totalmente responsivo com área rolável inteligente.
  - O botão de download (`⚡ BAIXAR AGORA`) e a barra de progresso ficam permanentemente ancorados no rodapé, nunca desaparecendo mesmo se a janela for redimensionada.
- **Detecção Cruzada Inteligente de Links:**
  - Se você estiver na aba do YouTube e colar um link do Twitter/X ou Instagram (ou vice-versa), o app reconhece a plataforma de destino e exibe um botão interativo: `[ Ir para Twitter / X e Analisar ➜ ]`. Ao clicar, a aba troca e a análise inicia automaticamente.
- **Limpeza Automática de Cache a Cada Análise:**
  - Cada vez que você clica em "Analisar", o cache temporário é redefinido e o card de prévia é renovado do zero, evitando travamentos ou sobreposição de capas de links anteriores.
- **Suporte Abrangente no Módulo Twitter / X:**
  - **Fotos e Imagens:** Detecção e download de posts com fotos em resolução original (`.jpg`/`.png`).
  - **Animações (.GIF):** Reconhecimento de GIFs com opção de download direto como `.gif` (gerado com paleta de 256 cores via FFmpeg) ou `.mp4`.
  - **Thumbnail Confiável:** Extração automática do primeiro frame (`00:00:00.1`) via FFmpeg para prévia instantânea da mídia.
- **Módulo Instagram (Fotos, Carrosséis e Vídeos/Reels):**
  - **Fotos e Posts:** Extração inteligente e download de imagens em resolução máxima original (`.jpg`), com contorno transparente de restrições de login/TLS.
  - **Reels e Vídeos:** Download direto em formato `.mp4` de alta qualidade.
  - **Metadados Completos:** Título, autor e capa carregados instantaneamente.
- **Módulo YouTube & Playlists Completas:**
  - **Vídeo Único (MP4):** Download com seleção de resoluções dinâmicas (720p, 1080p, 1440p 2K até 2160p 4K UHD).
  - **Áudio Puro (MP3):** Conversão automática na qualidade máxima de 320 kbps e metadados ID3 embutidos.
  - **Suporte Avançado a Playlists do YouTube:**
    - Extração rápida de todos os vídeos da playlist em lote.
    - **Lista Interativa Paginada:** Exibe 30 vídeos por página com navegação fluida (`◀ Anterior` e `Próxima ▶`).
    - **Seleção Individual por Checkbox:** Marque ou desmarque vídeos individualmente para baixar apenas o que desejar.
    - **Ações Rápidas em Massa:** Botões `Marcar Todos` e `Desmarcar Todos` com persistência de marcação entre páginas.
    - **Seleção de Qualidade Completa:** Opções de 4K UHD, 2K QHD, 1080p FHD, 720p HD até 360p para downloads da playlist.
    - **Organização Automática em Subpastas:** Os vídeos baixados da playlist são organizados em uma pasta própria com o nome da playlist e arquivos numerados ordenadamente (`01 - Nome.mp4`, `02 - Nome.mp4`, etc.).
  - **Download de Thumbnail:** Download direto da capa/miniatura em resolução máxima com um clique.
- **Telemetria Precisa e Suavizada de Velocidade e Tempo:**
  - Amortecedor inteligente de velocidade (`SpeedSmoother` com média móvel exponencial) para eliminar picos ilusórios de buffers/caches e refletir a velocidade real da conexão.
  - Estimativa realista de tempo restante (ETA), evitando contadores zerados prematuramente e calculando com exatidão o tempo restante da playlist inteira.
  - Status informativo de cada fase (download do vídeo, download do áudio e mesclagem final com FFmpeg).
- **Prévia de Tamanho Estimado de Arquivo:**
  - O menu de seleção de qualidade exibe o tamanho aproximado de cada arquivo antes de iniciar o download (ex: `2160p (4K UHD) ~ 12.3 GB`, `1080p (FHD) ~ 2.4 GB`, `MP3 320 kbps ~ 8.7 MB`, `Imagem ~ 201.5 KB`).
- **Auto-Diagnóstico & Instalação Automática do FFmpeg (1-Clique):**
  - Checagem automática de ambiente ao abrir o app (presença do FFmpeg, internet e permissões de escrita).
  - **Instalador Automático Integrado:** Se o sistema não tiver o FFmpeg, o app oferece um botão de instalação automática direta que baixa, extrai e configura os binários do FFmpeg sem necessidade de abrir navegador ou configurar variáveis de ambiente.

---

## 🎨 Paleta de Cores e Design

- **Fundo da Janela:** `#0D0E11` (Preto profundo)
- **Cards e Seções:** `#16171B` e `#1F2126` (Carvão suave)
- **Acento Primário (Brand Red):** `#E50914` (Vermelho vibrante)
- **Hover Primário:** `#B80710`
- **Texto Principal:** `#FFFFFF` (Branco absoluto)
- **Texto Secundário / Labels:** `#9CA3AF` (Cinza neutro)

---

## 🚀 Como Executar em Ambiente de Desenvolvimento

### Pré-requisitos
- **Python 3.9+** (recomendado Python 3.11+)
- **FFmpeg** (instalado no sistema ou baixado automaticamente pelo botão no primeiro uso)

### Instalação
```bash
# 1. Clone o repositório
git clone https://github.com/PatoDesoxigenado/NexusFetch.git
cd NexusFetch

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Execute o programa
python main.py
```

---

## 🧪 Testes Automatizados

O projeto conta com suíte de testes unitários para validadores regex, detecção de playlists, extração de metadados, estimativa de tamanhos e rotinas de diagnóstico:

```bash
python -m pytest tests/
```

---

## 📦 Compilação para Executável Standalone

### 🪟 1. Compilação para Windows (.exe)
Gera um executável portátil de um único arquivo na pasta `dist/NexusFetch.exe`, sem janela preta de console (`--noconsole`) e com ícone embutido:

- **Via Script Python:**
  ```cmd
  python build_exe.py
  ```
- **Via Arquivo Batch (1 clique):**
  Dê um duplo clique no arquivo `build.bat`.

---

### 🐧 2. Compilação para Linux (Binário ELF)
Para gerar o executável nativo de sistemas Linux (`dist/NexusFetch`):

> **⚠️ Importante sobre o Git Bash:** O Git Bash no Windows executa o Python do Windows (gerando `.exe`). Para compilar um binário nativo de Linux (formato ELF), execute em uma máquina Linux real ou pelo WSL do Windows.

- **Opção A: No Windows via WSL (com 1 clique ou terminal):**
  - Dê um duplo clique no arquivo `build_linux_via_wsl.bat`
  - Ou execute via terminal:
    ```cmd
    wsl -d Ubuntu -- bash -c 'cd "$(wslpath -u "$PWD")" && ./build_linux.sh'
    ```

- **Opção B: Em uma máquina ou Máquina Virtual Linux (Ubuntu, Debian, Fedora, Arch):**
  ```bash
  chmod +x build_linux.sh
  ./build_linux.sh
  ```

- **Integração com Desktop Linux:**
  O arquivo [NexusFetch.desktop](file:///C:/Users/Luiz/Documents/GitHub/NexusFetch/NexusFetch.desktop) já está incluso na raiz para integrar o aplicativo ao menu de programas e barra de tarefas do sistema operacional Linux.

---

## 📁 Estrutura do Projeto

```
NexusFetch/
├── .gitattributes             # Regras de normalização de quebras de linha (LF para Linux, CRLF para Windows)
├── .gitignore                 # Arquivos e diretórios ignorados pelo controle de versão
├── NexusFetch.desktop         # Atalho de integração com o menu de aplicativos no Linux (XDG)
├── README.md                  # Documentação completa e guia do projeto
├── requirements.txt           # Dependências Python (CustomTkinter, yt-dlp, Pillow, curl_cffi, etc.)
├── main.py                    # Ponto de entrada da aplicação
├── build.bat                  # Script de compilação em 1-clique para Windows
├── build_exe.py               # Automação de compilação PyInstaller para Windows (.exe)
├── build_linux.py             # Script de compilação para Linux (Python)
├── build_linux.sh             # Script de compilação para Linux (Bash standalone)
├── build_linux_via_wsl.bat    # Atalho para compilar o binário Linux a partir do Windows via WSL
├── dist/                      # Binários executáveis prontos para uso
│   ├── NexusFetch.exe         # Executável portátil para Windows 10/11
│   └── NexusFetch             # Executável ELF 64-bit nativo para Linux
├── assets/                    # Identidade visual e ícones do aplicativo
│   ├── icon.ico               # Ícone em formato Windows Icon
│   └── icon.png               # Ícone em formato PNG de alta resolução
├── logs/                      # Diretório de logs de execução (ignorado no Git)
│   └── nexus.log              # Registro de eventos e diagnósticos de execução
├── src/                       # Código-fonte modular da aplicação
│   ├── __init__.py
│   ├── config.py              # Constantes globais, temas, dimensões e caminhos de assets
│   ├── core/                  # Mecanismos centrais de dados e download
│   │   ├── __init__.py
│   │   ├── downloader.py      # Motor de download assíncrono (Vídeos, Áudios, GIFs, Fotos e Playlists)
│   │   └── metadata.py        # Extração de metadados, capas, frames e suporte a playlists
│   ├── ui/                    # Interface gráfica do usuário (CustomTkinter)
│   │   ├── __init__.py
│   │   ├── app.py             # Janela principal com fila thread-safe e orquestração de eventos
│   │   ├── theme.py           # Sistema de design (cores Nexus Red, tipografia e espaçamentos)
│   │   └── components/        # Componentes visuais modulares
│   │       ├── __init__.py
│   │       ├── diag_modal.py  # Modal de diagnóstico inicial com instalador do FFmpeg
│   │       ├── format_bar.py  # Barra de escolha de formatos, resoluções e diretório
│   │       ├── navbar.py      # Barra de navegação superior entre plataformas
│   │       ├── preview.py     # Card de prévia da mídia e lista interativa paginada de playlists
│   │       ├── progress.py    # Barra de progresso, métricas em tempo real e botão de ação
│   │       └── url_input.py   # Campo de inserção de URL com detecção cruzada inteligente
│   └── utils/                 # Módulos utilitários e diagnósticos
│       ├── __init__.py
│       ├── diagnostics.py     # Verificação de ambiente e instalador automático de FFmpeg
│       ├── helpers.py         # Formatadores de bytes, durações e higienização de arquivos
│       ├── logger.py          # Gerenciamento de logs thread-safe do sistema
│       └── validators.py      # Validação regex de URLs e detecção de playlists
└── tests/                     # Suíte de testes automatizados com pytest
    ├── test_diagnostics.py    # Testes de verificação de ambiente e permissões
    ├── test_downloader.py     # Testes de download, estrutura de playlists e cancelamento
    └── test_validators.py     # Testes de detecção de plataformas e URLs de playlists
```
