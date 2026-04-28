"""
Notion → Markdown 转换模块

用法:
    python -m app.core.notion_importer --database "your-database-id"
    python -m app.core.notion_importer --page "page-id"
    python -m app.core.notion_importer --search "query"  # 搜索页面
"""

import os
import asyncio
import hashlib
from pathlib import Path
from typing import Optional
from notion_client import AsyncClient
from dotenv import load_dotenv

# Load .env
load_dotenv()


class NotionImporter:
    """Import notes from Notion and convert to Markdown"""

    def __init__(self, token: str = None):
        self.token = token or os.getenv("NOTION_API_KEY")
        if not self.token:
            raise ValueError("NOTION_API_KEY not set")
        self.notion = AsyncClient(auth=self.token)

    def compute_id(self, text: str) -> str:
        """Generate deterministic ID"""
        return hashlib.md5(text.encode()).hexdigest()[:12]

    async def search_pages(self, query: str, limit: int = 50) -> list[dict]:
        """Search for pages matching query"""
        results = await self.notion.search(
            query=query,
            filter={'property': 'object', 'value': 'page'},
            page_size=limit
        )
        return results.get('results', [])

    async def get_page(self, page_id: str) -> dict:
        """Get a single page"""
        return await self.notion.pages.retrieve(page_id)

    async def get_page_blocks(self, page_id: str) -> list[dict]:
        """Get all blocks in a page"""
        blocks = []
        cursor = None

        while True:
            if cursor:
                response = await self.notion.blocks.children.list(
                    block_id=page_id,
                    start_cursor=cursor
                )
            else:
                response = await self.notion.blocks.children.list(block_id=page_id)

            blocks.extend(response.get('results', []))
            cursor = response.get('next_cursor')

            if not cursor:
                break

        return blocks

    def block_to_markdown(self, block: dict, depth: int = 0) -> str:
        """Convert a single Notion block to Markdown"""
        block_type = block.get('type', '')
        content = block.get(block_type, {})

        indent = '  ' * depth

        if block_type == 'paragraph':
            text = self._extract_text(content.get('rich_text', []))
            return f'{text}\n' if text else '\n'

        elif block_type == 'heading_1':
            text = self._extract_text(content.get('rich_text', []))
            return f'# {text}\n'

        elif block_type == 'heading_2':
            text = self._extract_text(content.get('rich_text', []))
            return f'## {text}\n'

        elif block_type == 'heading_3':
            text = self._extract_text(content.get('rich_text', []))
            return f'### {text}\n'

        elif block_type == 'bulleted_list_item':
            text = self._extract_text(content.get('rich_text', []))
            return f'{indent}- {text}\n'

        elif block_type == 'numbered_list_item':
            text = self._extract_text(content.get('rich_text', []))
            return f'{indent}1. {text}\n'

        elif block_type == 'to_do':
            checked = content.get('checked', False)
            text = self._extract_text(content.get('rich_text', []))
            checkbox = '[x]' if checked else '[ ]'
            return f'{indent}- {checkbox} {text}\n'

        elif block_type == 'code':
            text = self._extract_text(content.get('rich_text', []))
            language = content.get('language', '')
            return f'```{language}\n{text}\n```\n'

        elif block_type == 'quote':
            text = self._extract_text(content.get('rich_text', []))
            return f'> {text}\n'

        elif block_type == 'callout':
            text = self._extract_text(content.get('rich_text', []))
            icon = content.get('icon') or {}
            emoji = icon.get('emoji', '💡') if isinstance(icon, dict) else '💡'
            return f'> {emoji} {text}\n'

        elif block_type == 'divider':
            return '---\n'

        elif block_type == 'image':
            url = content.get('type') == 'external' \
                and content.get('external', {}).get('url') \
                or content.get('file', {}).get('url', '')
            caption = self._extract_text(content.get('caption', []))
            return f'![{caption}]({url})\n'

        elif block_type == 'bookmark':
            url = content.get('url', '')
            caption = self._extract_text(content.get('caption', []))
            return f'[{caption}]({url})\n'

        elif block_type == 'child_database':
            title = content.get('title', '')
            return f'[[Database: {title}]]\n'

        elif block_type == 'child_page':
            title = content.get('title', '')
            return f'[[{title}]]\n'

        elif block_type == 'embed':
            url = content.get('url', '')
            return f'[Embed]({url})\n'

        elif block_type == 'unsupported':
            return ''

        return ''

    def _extract_text(self, rich_text: list) -> str:
        """Extract plain text from Notion rich_text array"""
        if not rich_text:
            return ''

        parts = []
        for text in rich_text:
            if text.get('type') == 'text':
                t = text.get('text', {})
                content = t.get('content', '')
                ann = text.get('annotations', {})

                if ann.get('code'):
                    content = f'`{content}`'
                if ann.get('bold'):
                    content = f'**{content}**'
                if ann.get('italic'):
                    content = f'*{content}*'
                if ann.get('strikethrough'):
                    content = f'~~{content}~~'
                if ann.get('underline'):
                    content = f'__{content}__'

                link = t.get('link')
                if link and link.get('url'):
                    content = f'[{content}]({link["url"]})'

                parts.append(content)
            elif text.get('type') == 'mention':
                parts.append(text.get('plain_text', ''))
            elif text.get('type') == 'equation':
                parts.append(f'${text.get("equation", {}).get("expression", "")}$')

        return ''.join(parts)

    def get_page_title(self, page: dict) -> str:
        """Extract title from page properties"""
        props = page.get('properties', {})

        # Try common title property names
        for key in ['title', 'Name', '标题', 'name']:
            if key in props:
                val = props[key]
                if val.get('type') == 'title':
                    return self._extract_text(val.get('title', []))

        return 'Untitled'

    def get_page_tags(self, page: dict) -> list[str]:
        """Extract tags/multi-select from page"""
        tags = []
        props = page.get('properties', {})

        for key, val in props.items():
            if val.get('type') == 'multi_select':
                for item in val.get('multi_select', []):
                    tags.append(item.get('name', ''))
            elif val.get('type') == 'select':
                select = val.get('select')
                if select:
                    tags.append(select.get('name', ''))

        return tags

    async def import_page(self, page_id: str, output_dir: Path) -> Optional[Path]:
        """Import a single Notion page to Markdown"""
        try:
            page = await self.get_page(page_id)
        except Exception as e:
            print(f'Failed to get page {page_id}: {e}')
            return None

        title = self.get_page_title(page)
        tags = self.get_page_tags(page)

        # Get page content
        blocks = await self.get_page_blocks(page_id)
        markdown_content = self._blocks_to_markdown(blocks)

        # Build frontmatter
        frontmatter = f'''---
title: "{title}"
tags: [{', '.join(f'"{t}"' for t in tags)}]
source: notion
notion_id: "{page_id}"
created: {page.get('created_time', '')}
updated: {page.get('last_edited_time', '')}
---

'''

        # Write file
        safe_title = ''.join(c if c.isalnum() or c in '.-' else '_' for c in title[:50])
        filename = f'{self.compute_id(page_id)}-{safe_title}.md'
        output_path = output_dir / filename
        output_path.write_text(frontmatter + markdown_content, encoding='utf-8')

        print(f'Imported: {title}')
        return output_path

    async def import_database(self, database_id: str, output_dir: Path) -> list[Path]:
        """Import all items from a Notion database using search"""
        # Search for pages in the database
        paths = []
        try:
            results = await self.search_pages('', limit=100)
            for page in results:
                page_id = page.get('id')
                if page_id:
                    path = await self.import_page(page_id, output_dir)
                    if path:
                        paths.append(path)
        except Exception as e:
            print(f'Error importing database: {e}')
        return paths

    def _blocks_to_markdown(self, blocks: list[dict]) -> str:
        """Convert blocks to markdown (synchronous)"""
        lines = []
        i = 0

        while i < len(blocks):
            block = blocks[i]
            block_type = block.get('type', '')

            md = self.block_to_markdown(block)
            if md:
                lines.append(md)

            # Note: children handling removed for simplicity
            # Can be added with async recursive approach

            i += 1

        return ''.join(lines)


async def main():
    import argparse

    parser = argparse.ArgumentParser(description='Notion → Markdown Importer')
    parser.add_argument('--database', help='Database ID to import')
    parser.add_argument('--page', help='Single page ID to import')
    parser.add_argument('--search', help='Search query to import matching pages')
    parser.add_argument('--output', default='data/notes', help='Output directory')
    parser.add_argument('--token', help='Notion API token (or set NOTION_API_KEY)')

    args = parser.parse_args()

    token = args.token or os.getenv('NOTION_API_KEY')
    if not token:
        print('Error: NOTION_API_KEY not set')
        print('Get one at: https://www.notion.so/my-integrations')
        return

    importer = NotionImporter(token=token)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.page:
        await importer.import_page(args.page, output_dir)
    elif args.database:
        await importer.import_database(args.database, output_dir)
    elif args.search:
        results = await importer.search_pages(args.search)
        print(f'Found {len(results)} pages matching "{args.search}"')
        for page in results:
            title = importer.get_page_title(page)
            print(f'  - {title} ({page.get("id")})')
        # Import all results
        print(f'\nImporting all {len(results)} pages...')
        for page in results:
            await importer.import_page(page.get('id'), output_dir)
    else:
        parser.print_help()
        return

    print(f'\nImport complete! Files saved to {output_dir}')


if __name__ == '__main__':
    asyncio.run(main())
