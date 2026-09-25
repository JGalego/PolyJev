#!/usr/bin/env bash
# Status lines for make and just.  fun.sh say EMOJI TEXT | ok TEXT | fail TEXT | bar DONE TOTAL TEXT [START]
# Colors only on a terminal, and never with NO_COLOR set.
set -euo pipefail

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    B=$'\e[1m' D=$'\e[2m' G=$'\e[32m' R=$'\e[31m' C=$'\e[36m' N=$'\e[0m'
else
    B='' D='' G='' R='' C='' N=''
fi

since() { local s=$(($(date +%s) - $1)); printf '%dm%02ds' $((s / 60)) $((s % 60)); }

case $1 in
    say) printf '%s\n' "${B}$2 $3${N}" ;;
    ok) printf '%s\n' "${G}${B}✅ $2${N}" ;;
    fail) printf '%s\n' "${R}${B}💥 $2${N}" >&2 ;;
    bar)
        done=$2 total=$3 width=24
        full=$((done * width / total))
        printf -v on '%*s' "$full" ''
        printf -v off '%*s' $((width - full)) ''
        clock=${5:+"  ${D}⏱  $(since "$5")${N}"}
        printf '\n%s\n' "${C}${on// /█}${off// /░}${N} ${B}$((done * 100 / total))%  $4${N}${clock}"
        ;;
    *) echo "usage: fun.sh say|ok|fail|bar ..." >&2; exit 2 ;;
esac
