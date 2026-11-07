#!/usr/bin/env bash
# Generates ldap/ldif/50-conote-seed.ldif with salted password hashes.
set -euo pipefail
cd "$(dirname "$0")"
source ../.env
: "${LDAP_TEST_PASSWORD:?set LDAP_TEST_PASSWORD in iam/.env}"

ssha() {  # salted SHA-1 hash, the format OpenLDAP expects ({SSHA})
  python3 -c 'import hashlib,os,base64,sys
s=os.urandom(8); print("{SSHA}"+base64.b64encode(hashlib.sha1(sys.argv[1].encode()+s).digest()+s).decode())' "$1"
}

ou() { printf 'dn: ou=%s,dc=conote,dc=edu\nobjectClass: organizationalUnit\nou: %s\ndescription: %s\n\n' "$1" "$1" "$2"; }

# user <uid> <ou> <firstName> <lastName> <department> [studentId]
user() {
  printf 'dn: uid=%s,ou=%s,dc=conote,dc=edu\nobjectClass: inetOrgPerson\nuid: %s\ncn: %s %s\ngivenName: %s\nsn: %s\nmail: %s@conote.edu\ndepartmentNumber: %s\n' \
    "$1" "$2" "$1" "$3" "$4" "$3" "$4" "$1" "$5"
  if [ -n "${6:-}" ]; then printf 'employeeNumber: %s\n' "$6"; fi
  printf 'userPassword: %s\n\n' "$(ssha "$LDAP_TEST_PASSWORD")"
}

# group <cn> <member DN>...
group() {
  local cn=$1; shift
  printf 'dn: cn=%s,ou=groups,dc=conote,dc=edu\nobjectClass: groupOfNames\ncn: %s\n' "$cn" "$cn"
  for m in "$@"; do printf 'member: %s\n' "$m"; done
  printf '\n'
}

mkdir -p ldif
{
     printf 'dn: cn=keycloak-bind,ou=services,dc=conote,dc=edu\nobjectClass: organizationalRole\nobjectClass: simpleSecurityObject\ncn: keycloak-bind\ndescription: Read-only bind account used by Keycloak user federation\nuserPassword: %s\n\n' "$(ssha "$KC_LDAP_BIND_PASSWORD")"

  printf 'dn: dc=conote,dc=edu\nobjectClass: dcObject\nobjectClass: organization\ndc: conote\no: Co-Note Institution\n\n'
  ou students       "Student accounts"
  ou teachers       "Teaching staff accounts"
  ou administrators "Administrative and IT staff accounts"
  ou groups         "Access groups"
  ou services       "Service (non-human) accounts"

  user student01 students       Amina Bello   "Computer Science" S2026001
  user student02 students       Paul  Nkeng   "Cybersecurity"    S2026002
  user teacher01 teachers       Grace Fon     "Cybersecurity"
  user teacher02 teachers       Eric  Tabi    "Computer Science"
  user admin01   administrators Diane Mbah    "Administration"
  user support01 administrators Kevin Ewane   "IT Support"

  group students       uid=student01,ou=students,dc=conote,dc=edu uid=student02,ou=students,dc=conote,dc=edu
  group teachers       uid=teacher01,ou=teachers,dc=conote,dc=edu uid=teacher02,ou=teachers,dc=conote,dc=edu
  group administrators uid=admin01,ou=administrators,dc=conote,dc=edu
  group it-support     uid=support01,ou=administrators,dc=conote,dc=edu
} > ldif/50-conote-seed.ldif

echo "Wrote $(grep -c '^dn:' ldif/50-conote-seed.ldif) entries to ldif/50-conote-seed.ldif"
