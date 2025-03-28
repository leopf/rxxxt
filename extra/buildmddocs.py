from mkdocs.commands.build import build
from mkdocs.config import load_config
from mkdocs.plugins import BasePlugin
from markdownify import markdownify
import os

class MarkdownExtractorPlugin(BasePlugin):
    def on_page_content(self, html, page, config, files):
        # Define the output directory
        output_dir = os.path.join(config['site_dir'], '..', 'mdsite')

        # Ensure the mdside/ directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Create a safe filename based on the page's source path
        # Replace slashes with underscores to avoid subdirectories
        filename = page.file.src_path.replace(os.sep, '_').replace('.md', '') + '.md'
        output_path = os.path.join(output_dir, filename)

        # Write the raw Markdown content to a file in mdside/
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdownify(html))

        # Log the action (optional, for debugging)
        self.log(f"Saved Markdown for {page.file.src_path} to {output_path}")

        # Return the markdown unchanged to continue the build process
        return html

    def log(self, message):
        # Simple logging to console; you can enhance this if needed
        print(f"[MarkdownExtractor] {message}")


# Load the MkDocs configuration from mkdocs.yml
config = load_config("mkdocs.yml")
config.plugins["markdown_extractor"] = MarkdownExtractorPlugin()

build(config)
