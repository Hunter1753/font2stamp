## How it works

This app

- installs the fonts you have in the project root folder into the newly created container
- runs the script to generate openscad files and render them with openscad to "stl_output/"

### Build Image

```bash
podman build -t stamp-generator
```

### Running generator

```bash
podman run --rm -v "$(pwd):/app" stamp-generator
```

### Methodology and AI Assistance
This program was written by hand. Large Language Models (specifically Gemini) were used during the ideation phase and to provide example code snippets for openscad. All AI-generated suggestions were reviewed, modified, and implemented by the author.
