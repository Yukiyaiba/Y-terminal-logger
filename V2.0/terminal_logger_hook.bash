# Source at the end of ~/.bashrc, after other prompt settings (Bash >= 5.1).
[[ $- == *i* && ${TERMINAL_LOGGER_ACTIVE:-} == 1 ]] || return 0
[[ -n ${TERMINAL_LOGGER_COMMAND_FILE:-} ]] || return 0
# A shell-local guard: nested Bash sessions must install their own hook.
[[ ${_terminal_logger_hook_pid:-} != "$$" ]] || return 0
_terminal_logger_hook_pid=$$

_terminal_logger_prompt() {
    local status=$?
    # Do not clear/reload history or change the user's persistence settings.
    _terminal_logger_last_entry=$(HISTTIMEFORMAT= builtin history 1)
    return "$status"
}

_terminal_logger_before_command() {
    [[ -o history ]] || return 0
    local entry command timestamp
    entry=$(HISTTIMEFORMAT= builtin history 1) || return 0
    [[ -n $entry && $entry != "${_terminal_logger_last_entry-}" ]] || return 0
    [[ $entry =~ ^[[:space:]]*[0-9]+[[:space:]][[:space:]] ]] || return 0
    command=${entry:${#BASH_REMATCH[0]}}
    printf -v timestamp '%(%Y-%m-%d %H:%M:%S)T' -1
    printf '%s\0%s\0' "$timestamp" "$command" >> "$TERMINAL_LOGGER_COMMAND_FILE" ||
        printf 'terminal logger: cannot append command record\n' >&2
}

# Insert first so other prompt handlers still see the command's exit status.
case $(declare -p PROMPT_COMMAND 2>/dev/null) in
    "declare -a "*) PROMPT_COMMAND=(_terminal_logger_prompt "${PROMPT_COMMAND[@]}") ;;
    *)
        if [[ -n ${PROMPT_COMMAND-} ]]; then
            PROMPT_COMMAND=(_terminal_logger_prompt "$PROMPT_COMMAND")
        else
            PROMPT_COMMAND=(_terminal_logger_prompt)
        fi
        ;;
esac

shopt -s promptvars
PS0="${PS0-}"'$(_terminal_logger_before_command)'
