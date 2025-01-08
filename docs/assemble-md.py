import os
import sys
import markdown2

def adjust_image_paths(content, current_file_dir, output_base_dir):
    """
    Adjust relative image paths to be relative to the output base directory and use forward slashes.
    """
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if '](' in line:
        #if '![' in line and '](' in line:
            start_link = line.find('](') + 2
            end_link = line.find(')', start_link)
            relative_path = line[start_link:end_link]
            if not os.path.isabs(relative_path):
                # Calculate the relative path from the current file directory to the image
                image_path = os.path.normpath(os.path.join(current_file_dir, relative_path))
                relative_to_output = os.path.relpath(image_path, output_base_dir)
                # Convert backslashes to forward slashes
                relative_to_output = relative_to_output.replace('\\', '/')
                lines[i] = line[:start_link] + relative_to_output + line[end_link:]
    return '\n'.join(lines)

def assemble_markdown_files(index_file, output_file_base):
    markdown_content = ""
    toc_content = ""
    base_path = os.path.dirname(os.path.abspath(index_file))
    output_base_dir = os.path.dirname(os.path.abspath(output_file_base + '.md'))

    with open(index_file, 'r') as file:
        lines = file.readlines()
    
    for line in lines:
        if ' [' in line:
            start_link = line.find('(') + 1
            end_link = line.find(')')
            file_link = line[start_link:end_link].strip()
            file_path = os.path.normpath(os.path.join(base_path, file_link))

            # Generate clean anchors for ToC links
            anchor_link = f'#{os.path.basename(file_link).replace(".md", "").replace(" ", "-").lower()}'
            toc_line = line.replace(file_link, anchor_link)
            toc_content += toc_line
            
            # Check file type and skip non-markdown files
            if file_link.lower().endswith('.md') and os.path.exists(file_path):
                with open(file_path, 'r') as infile:
                    file_contents = infile.read()
                    file_contents = adjust_image_paths(file_contents, os.path.dirname(file_path), output_base_dir)
                    file_contents = file_contents.replace("\n#", "\n##")  # Downgrade headers
                    markdown_content += f"\n<a id='{os.path.basename(file_link).replace('.md', '').replace(' ', '-').lower()}'></a>\n\n----\n\n"
                    markdown_content += file_contents + '\n'
            elif not file_link.lower().endswith('.md'):
                toc_content += f" (External file not included in compilation)\n"
            else:
                markdown_content += f"# File not found: {file_link}\n\n"
        else:
            toc_content += line
            markdown_content += line

    complete_markdown = toc_content + markdown_content
    with open(output_file_base + '.md', 'w') as outfile:
        outfile.write(complete_markdown)

if __name__ == "__main__":
    index_filename = 'README.md'
    output_filename_base = 'Complete'
    
    if len(sys.argv) > 1:
        index_filename = sys.argv[1]
    if len(sys.argv) > 2:
        output_filename_base = sys.argv[2]
    
    assemble_markdown_files(index_filename, output_filename_base)
