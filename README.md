# 🔻 Nexus Fetch

> **Baixe vídeos, áudios, imagens e playlists de forma limpa, direta e 100% segura.**  
> Sem anúncios invasivos, sem pop-ups, sem redirecionamentos suspeitos e sem vírus.

[![Versão](https://img.shields.io/badge/vers%C3%A3o-1.0.0-E50914.svg)](https://github.com/PatoDesoxigenado/NexusFetch/releases)
[![Licença](https://img.shields.io/badge/licen%C3%A7a-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-brightgreen.svg)](https://www.python.org/)
[![Plataformas](https://img.shields.io/badge/plataformas-Windows%20%7C%20Linux-lightgrey.svg)](https://github.com/PatoDesoxigenado/NexusFetch/releases)

---

## 📥 Baixar o Programa (Pronto para Usar - Não Precisa Instalar)

O **NexusFetch** é um aplicativo portátil (*standalone*). Você não precisa instalar nada no seu computador nem configurar variáveis de ambiente: basta baixar o executável referente ao seu sistema e abrir com dois cliques.

| Sistema Operacional | Arquivo | Tamanho | Download Direto |
| :--- | :--- | :--- | :--- |
| **🪟 Windows (10/11 - 64-bit)** | `NexusFetch.exe` | ~53 MB | [⬇️ **Baixar para Windows (.exe)**](https://github.com/PatoDesoxigenado/NexusFetch/raw/main/dist/NexusFetch.exe) |
| **🐧 Linux (Ubuntu, Debian, Fedora, Arch)** | `NexusFetch` | ~47 MB | [⬇️ **Baixar para Linux (Binário)**](https://github.com/PatoDesoxigenado/NexusFetch/raw/main/dist/NexusFetch) |

> 💡 **Usuários Linux:** Após baixar, abra o terminal na pasta do arquivo e libere permissão de execução:  
> `chmod +x NexusFetch && ./NexusFetch`

---

## 📖 Como Usar (Passo a Passo Rápido)

1. **Abra o programa** dando dois cliques no executável.
2. **Cole o link** da mídia que você quer baixar (o programa aceita **YouTube**, **Instagram** e **Twitter / X**).
3. Clique em **Analisar**.
4. **Escolha o formato e a qualidade desejada:**
   - **Vídeo (MP4):** De 360p até 4K UHD (2160p).
   - **Áudio (MP3):** Conversão em altíssima fidelidade (320 kbps).
   - **Playlists do YouTube:** Selecione individualmente os vídeos que quer baixar com as caixas de seleção ou use os botões *Marcar Todos* / *Desmarcar Todos*.
   - **Imagens / GIFs:** Baixe fotos originais ou salve GIFs diretamente em formato `.gif`.
5. Clique em **Baixar**! O arquivo será salvo diretamente na sua pasta de **Downloads**.

> 🛠️ **E o FFmpeg?**  
> Para juntar áudio e vídeo em alta resolução ou converter para MP3, o programa precisa do FFmpeg. Ao abrir o NexusFetch, ele verifica isso automaticamente. Se você não tiver o FFmpeg instalado, **o próprio programa exibe um botão de 1 clique que baixa e configura tudo sozinho**, sem você precisar abrir navegador nem mexer em configurações do sistema!

---

## 🛡️ Por que o NexusFetch é Seguro e Confiável?

A grande maioria dos sites e programas online para baixar vídeos está repleta de:
- Anúncios enganosos e botões falsos de download;
- Rastreadores e mineradores em segundo plano;
- Riscos de adwares, malwares e vírus.

O **NexusFetch** nasceu para ser uma **alternativa definitiva, transparente e ética**:
- **100% Open Source:** Todo o código-fonte está aberto aqui no GitHub para qualquer pessoa auditar.
- **Zero Rastreamento:** O aplicativo não coleta seus dados, não exige login para uso básico e não envia nenhuma informação pessoal para servidores externos.
- **Sem Anúncios:** Interface limpa, moderna e focada na experiência do usuário.
- **Processamento 100% Local:** Todo o download e conversão ocorrem diretamente na sua máquina via bibliotecas consolidadas.

### ⚙️ Bibliotecas e Ferramentas Utilizadas por Baixo dos Panos:
- **[CustomTkinter](https://github.com/TomSchimansky/CustomTkinter):** Interface gráfica nativa moderna em Dark Mode, fluida, responsiva e sem sobrecarregar a memória.
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp):** A biblioteca open source mais respeitada e mantida do mundo para extração segura de mídias do YouTube.
- **[curl_cffi](https://github.com/yifeikong/curl_cffi):** Motor de requisições de rede que garante conexões seguras e contorna bloqueios de CDN do Instagram/Meta.
- **[FFmpeg](https://ffmpeg.org/):** Padrão da indústria para multiplexação e conversão de mídia em tempo real.
- **Auto-Updater Inteligente:** O aplicativo possui verificação automática de novas versões do motor yt-dlp e do próprio executável diretamente pelo repositório oficial do GitHub.

---

## ✨ Principais Recursos

- **YouTube & Playlists:**
  - Suporte de 360p a 4K UHD (2160p) com estimativa de tamanho do arquivo em tempo real.
  - Conversão para MP3 em 320 kbps com tags ID3.
  - Gerenciamento de playlists com paginação (30 itens por página), seleção em lote e organização automática em subpastas numeradas.
- **Instagram:**
  - Extração e download de fotos em resolução máxima original (`.jpg`).
  - Download de Reels e vídeos em alta resolução (`.mp4`).
- **Twitter / X:**
  - Download de fotos em qualidade original.
  - Download de vídeos e conversão nativa de animações para `.gif` (paleta otimizada de 256 cores).
- **Telemetria Suavizada:**
  - Cálculo de velocidade e tempo restante (ETA) com média móvel exponencial para eliminar picos falsos e exibir a velocidade real da sua rede.

---

## 💻 Guia para Desenvolvedores (Rodar pelo Código-Fonte)

Se você é desenvolvedor e deseja executar ou contribuir com o projeto a partir do código Python:

### 1. Clonar o Repositório e Instalar Dependências
```bash
# Clone o repositório
git clone https://github.com/PatoDesoxigenado/NexusFetch.git
cd NexusFetch

# Instale os pacotes necessários
pip install -r requirements.txt
```

### 2. Executar a Aplicação
```bash
python main.py
```

### 3. Rodar a Suíte de Testes
```bash
python -m pytest tests/
```

### 4. Compilar os Executáveis Standalone
- **Para Windows (.exe):**
  ```cmd
  python build_exe.py
  # Ou execute diretamente build.bat
  ```
- **Para Linux (Binário x86_64):**
  ```bash
  chmod +x build_linux.sh
  ./build_linux.sh
  ```

---

## 📂 Estrutura do Repositório

```text
NexusFetch/
├── assets/                     # Ícones e recursos visuais da aplicação
│   ├── icon.ico                # Ícone nativo para Windows
│   └── icon.png                # Ícone nativo para Linux
├── dist/                       # Executáveis compilados prontos para uso
│   ├── NexusFetch.exe          # Executável portátil para Windows (64-bit)
│   ├── NexusFetch              # Executável portátil para Linux (x86_64)
│   └── README.md               # Guia rápido de uso dos executáveis
├── src/                        # Código-fonte principal da aplicação
│   ├── config.py               # Configurações globais e diretórios
│   ├── core/                   # Núcleo de extração e download
│   │   ├── downloader.py       # Gerenciador de downloads e telemetria
│   │   └── metadata.py         # Extrator de metadados (YT, Insta, Twitter)
│   ├── ui/                     # Interface gráfica do usuário (CustomTkinter)
│   │   ├── app.py              # Janela principal e orquestração de eventos
│   │   ├── theme.py            # Cores, fontes e constantes visuais
│   │   └── components/         # Componentes modulares de UI
│   │       ├── navbar.py       # Cabeçalho com abas, botão GitHub e updater
│   │       ├── url_input.py    # Barra de entrada de link e status
│   │       ├── preview.py      # Cartão de prévia e listagem de playlists
│   │       ├── format_bar.py   # Seletor de qualidade e botões de ação
│   │       ├── progress.py     # Barra de progresso e métricas
│   │       └── diag_modal.py   # Modal de diagnóstico e instalador do FFmpeg
│   └── utils/                  # Utilitários auxiliares
│       ├── diagnostics.py      # Verificação de ambiente e instalador FFmpeg
│       ├── helpers.py          # Formatação de bytes, duração e SSL
│       ├── logger.py           # Sistema de logs rotativos em arquivo
│       ├── updater.py          # Auto-update do yt-dlp e do NexusFetch
│       └── validators.py       # Validação e detecção regex de links
├── tests/                      # Suíte de testes unitários automatizados
│   ├── test_diagnostics.py     # Testes de diagnóstico de sistema
│   ├── test_downloader.py      # Testes de download e estimativas
│   ├── test_updater.py         # Testes dos mecanismos de auto-update
│   └── test_validators.py      # Testes de URLs e detecção de plataformas
├── build_exe.py                # Script de compilação PyInstaller para Windows
├── build_linux.sh              # Script de compilação PyInstaller para Linux
├── build.bat                   # Atalho de compilação em 1 clique para Windows
├── main.py                     # Ponto de entrada do aplicativo
├── requirements.txt            # Dependências Python do projeto
└── README.md                   # Documentação oficial
```

---

## 📄 Licença

Distribuído sob a licença **MIT**. Veja o arquivo `LICENSE` para mais detalhes.
