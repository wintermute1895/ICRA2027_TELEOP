#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "${script_dir}/.." && pwd)"
output_path="${1:-${project_dir}/dist/ICRA2027_overleaf.zip}"

if [[ "${output_path}" != /* ]]; then
  output_path="${project_dir}/${output_path}"
fi

stage_dir="$(mktemp -d /tmp/icra-overleaf.XXXXXX)"
archive_dir="$(mktemp -d /tmp/icra-overleaf-archive.XXXXXX)"
archive_tmp="${archive_dir}/ICRA2027_overleaf.zip"
trap 'rm -rf "${stage_dir}" "${archive_dir}"' EXIT

mkdir -p "${stage_dir}/sections" "${stage_dir}/figures"
install -m 0644 "${project_dir}/main.tex" "${stage_dir}/main.tex"
install -m 0644 "${project_dir}/bib_controls.bib" "${stage_dir}/bib_controls.bib"
install -m 0644 "${project_dir}/references.bib" "${stage_dir}/references.bib"
install -m 0644 "${project_dir}"/sections/*.tex "${stage_dir}/sections/"
install -m 0644 "${project_dir}"/figures/*.tex "${stage_dir}/figures/"

(
  cd "${stage_dir}"
  zip -q -r "${archive_tmp}" .
)

mkdir -p "$(dirname "${output_path}")"
mv "${archive_tmp}" "${output_path}"

printf 'Created %s\n' "${output_path}"
unzip -Z1 "${output_path}"
