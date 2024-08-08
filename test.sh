#!/bin/sh

rc='\033[0m'
red='\033[0;31m'

# Initialize progress bar
progress=0
total_steps=10  # Adjust this number based on the number of steps in your script

draw_progress() {
    width=50
    filled=$((progress * width / total_steps))
    empty=$((width - filled))

    # Create the progress bar
    bar=$(printf "%-${filled}s" | tr ' ' '#')
    empty_space=$(printf "%-${empty}s" | tr ' ' '.')

    printf "\rProgress: [%-${width}s] %d%%" "$bar$empty_space" $((progress * 100 / total_steps))
}

check() {
    exit_code=$1
    message=$2

    if [ "$exit_code" -ne 0 ]; then
        printf '\n%sERROR: %s%s\n' "$red" "$message" "$rc"
        exit 1
    fi

    unset exit_code
    unset message

    progress=$((progress + 1))
    draw_progress
}

findArch() {
    progress=$((progress + 1))
    draw_progress

    case "$(uname -m)" in
        x86_64|amd64) arch="x86_64" ;;
        aarch64|arm64) arch="aarch64" ;;
        *) check 1 "Unsupported architecture"
    esac
}

getUrl() {
    progress=$((progress + 1))
    draw_progress

    case "${arch}" in
        x86_64) echo "https://github.com/ChrisTitusTech/linutil/releases/latest/download/linutil";;
        *) echo "https://github.com/ChrisTitusTech/linutil/releases/latest/download/linutil-${arch}";;
    esac
}

# Start of the script
progress=$((progress + 1))
draw_progress

findArch

temp_file=$(mktemp)
check $? "Creating the temporary file"

progress=$((progress + 1))
draw_progress

curl -fsL "$(getUrl)" -o "$temp_file"
check $? "Downloading linutil"

progress=$((progress + 1))
draw_progress

chmod +x "$temp_file"
check $? "Making linutil executable"

progress=$((progress + 1))
draw_progress

"$temp_file"
check $? "Executing linutil"

progress=$((progress + 1))
draw_progress

rm -f "$temp_file"
check $? "Deleting the temporary file"

progress=$((progress + 1))
draw_progress

printf '\nScript completed successfully!\n'
