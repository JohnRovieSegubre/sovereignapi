import sys
import difflib

def clean_remote_content(content):
    lines = content.splitlines()
    # Remove header/footer from debug_cloud_file.ps1
    start_idx = 0
    end_idx = len(lines)
    
    for i, line in enumerate(lines):
        if line.strip() == "----------------------------------------" and i < 10:
            start_idx = i + 1
        if line.strip() == "----------------------------------------" and i > len(lines) - 5:
            end_idx = i
            
    return lines[start_idx:end_idx]

def compare(local_file, remote_file):
    with open(local_file, 'r', encoding='utf-8') as f:
        local_lines = f.read().splitlines()
        
    with open(remote_file, 'r', encoding='utf-16') as f: # PowerShell uses UTF-16
        remote_content = f.read()
        remote_lines = clean_remote_content(remote_content)

    diff = difflib.unified_diff(
        remote_lines, 
        local_lines, 
        fromfile='Remote (Cloud)', 
        tofile='Local (New)', 
        n=3
    )
    
    print("\n".join(diff))

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    compare(sys.argv[1], sys.argv[2])
