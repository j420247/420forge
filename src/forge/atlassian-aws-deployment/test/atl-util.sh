function atl_unquote {
    read quoted
    temp="${quoted%\"}"
    temp="${temp#\"}"
    echo "$temp"
}
