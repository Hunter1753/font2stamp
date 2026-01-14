FROM python:3.9-slim-bullseye

# 1. Install System Dependencies
RUN apt-get update && apt-get install -y \
    openscad \
    fontconfig \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Python Dependencies
# Added 'fonttools' to read font metadata
RUN pip install Pillow fonttools

# 3. Set up working directory
WORKDIR /app

# 4. Entrypoint Script
# - Copies fonts to system folder
# - Updates cache
# - Runs script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
echo "--- Checking for fonts in /app ---"\n\
if ls /app/*.ttf 1> /dev/null 2>&1; then cp /app/*.ttf /usr/share/fonts/; fi\n\
if ls /app/*.otf 1> /dev/null 2>&1; then cp /app/*.otf /usr/share/fonts/; fi\n\
\n\
echo "--- Rebuilding Font Cache ---"\n\
fc-cache -f -v\n\
\n\
echo "--- Running Stamp Generator ---"\n\
xvfb-run -a python3 font_to_stamps.py\n\
\n\
echo "--- Done! Exiting container. ---"\n\
' > /usr/local/bin/entrypoint.sh

RUN chmod +x /usr/local/bin/entrypoint.sh
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]