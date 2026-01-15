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
