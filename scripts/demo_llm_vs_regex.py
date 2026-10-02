#!/usr/bin/env python3
"""
Demo: Comparación Detección Regex vs. LLM
Muestra las limitaciones del análisis actual basado en keywords
"""
import re
import json

# Simulación del output real de sslscan
SSLSCAN_OUTPUT = """
Testing SSL server 10.19.220.25 on port 8088

  SSL/TLS Protocols:
  SSLv2     disabled
  SSLv3     enabled
  TLSv1.0   enabled
  TLSv1.1   enabled
  TLSv1.2   enabled
  TLSv1.3   disabled

  TLS Fallback SCSV:
  Server does not support TLS Fallback SCSV

  TLS renegotiation:
  Secure session renegotiation supported

  TLS Compression:
  Compression disabled

  Heartbleed:
  TLS 1.2 not vulnerable to heartbleed

  Supported Server Cipher(s):
  Accepted  TLSv1.0  256 bits  ECDHE-RSA-AES256-SHA
  Accepted  TLSv1.0  128 bits  ECDHE-RSA-AES128-SHA
  Accepted  TLSv1.0  128 bits  RC4-SHA
  Accepted  SSLv3    128 bits  RC4-SHA

  Certificate information:
  Subject:  10.19.220.25
  Issuer:   10.19.220.25
  Signature Algorithm: sha256WithRSAEncryption
  Valid From: Jan  1 00:00:00 2020 GMT
  Valid To:   Dec 31 23:59:59 2029 GMT
  Self-signed: yes
"""

# Simulación de análisis REGEX (método actual del MVP)
def analyze_with_regex(output: str) -> list[dict]:
    """Simula _analyze_for_findings() actual del orchestrator"""
    findings = []
    output_lower = output.lower()
    
    # Check for SSL/TLS issues (muy simple)
    if any(kw in output_lower for kw in ["ssl", "tls", "cipher"]):
        if any(issue in output_lower for issue in ["weak", "vulnerable", "insecure"]):
            findings.append({
                "severity": "medium",
                "title": "SSL/TLS Configuration Issues",
                "description": "Weak or insecure SSL/TLS configuration detected",
                "evidence": output[:200],  # Truncado
                "cwe": "CWE-327"
            })
    
    return findings


# Simulación de análisis LLM (lo que haría un LLM con comprensión semántica)
def analyze_with_llm_simulation(output: str) -> list[dict]:
    """Simula lo que haría un LLM analizando el output"""
    findings = []
    
    # LLM detectaría SSLv3 enabled
    if "SSLv3     enabled" in output:
        findings.append({
            "severity": "high",
            "title": "SSLv3 Protocol Enabled - POODLE Vulnerability (CVE-2014-3566)",
            "description": "The server accepts SSLv3 connections, making it vulnerable to the POODLE attack. An attacker on the network can decrypt secure connections by forcing a downgrade to SSLv3 and exploiting CBC cipher weaknesses. SSLv3 has been deprecated since 2015 and should be completely disabled.",
            "evidence": "SSLv3     enabled\nAccepted  SSLv3    128 bits  RC4-SHA",
            "cwe": "CWE-327",
            "cvss_score": 7.4,
            "cvss_vector": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:N",
            "exploit_available": True,
            "references": [
                "CVE-2014-3566",
                "https://www.openssl.org/~bodo/ssl-poodle.pdf"
            ],
            "remediation": "1. Disable SSLv3 in Apache configuration:\n   SSLProtocol all -SSLv2 -SSLv3\n2. Restart web server\n3. Verify with: nmap --script ssl-enum-ciphers -p 8088 10.19.220.25"
        })
    
    # LLM detectaría RC4 cipher
    if "RC4-SHA" in output:
        findings.append({
            "severity": "high",
            "title": "Weak Cipher Suite RC4-SHA Accepted",
            "description": "Server accepts RC4-SHA cipher which has known cryptographic weaknesses. RC4 is prohibited by RFC 7465 due to statistical biases that allow recovery of plaintext. This affects both SSLv3 and TLSv1.0 connections.",
            "evidence": "Accepted  TLSv1.0  128 bits  RC4-SHA\nAccepted  SSLv3    128 bits  RC4-SHA",
            "cwe": "CWE-327",
            "cvss_score": 5.3,
            "cvss_vector": "CVSS:3.1/AV:N/AC:H/PR:N/UI:R/S:U/C:H/I:N/A:N",
            "exploit_available": False,
            "references": [
                "RFC 7465",
                "https://www.rc4nomore.com/"
            ],
            "remediation": "Configure Apache to use only strong ciphers:\nSSLCipherSuite HIGH:!aNULL:!MD5:!RC4:!DES\nSSLHonorCipherOrder on"
        })
    
    # LLM detectaría certificado auto-firmado
    if "Self-signed: yes" in output:
        findings.append({
            "severity": "medium",
            "title": "Self-Signed SSL Certificate in Use",
            "description": "Server uses a self-signed certificate not issued by a trusted CA. While the connection is encrypted, users cannot verify the server's identity, making Man-in-the-Middle attacks possible if users accept the certificate warning.",
            "evidence": "Subject:  10.19.220.25\nIssuer:   10.19.220.25\nSelf-signed: yes",
            "cwe": "CWE-295",
            "cvss_score": 5.9,
            "exploit_available": False,
            "remediation": "1. Obtain certificate from trusted CA (Let's Encrypt is free)\n2. Install certificate in Apache\n3. For internal use: Deploy internal CA and distribute root cert to clients"
        })
    
    # LLM detectaría falta de TLS Fallback SCSV
    if "does not support TLS Fallback SCSV" in output:
        findings.append({
            "severity": "medium",
            "title": "Missing TLS Fallback SCSV Protection",
            "description": "Server does not support TLS_FALLBACK_SCSV, making it potentially vulnerable to protocol downgrade attacks where an attacker forces the connection to use an older, weaker protocol version.",
            "evidence": "TLS Fallback SCSV:\nServer does not support TLS Fallback SCSV",
            "cwe": "CWE-757",
            "cvss_score": 5.9,
            "remediation": "Update OpenSSL to version that supports RFC 7507 and enable SCSV support"
        })
    
    # LLM detectaría TLSv1.0/1.1 obsoletos
    if "TLSv1.0   enabled" in output or "TLSv1.1   enabled" in output:
        findings.append({
            "severity": "low",
            "title": "Obsolete TLS Versions Enabled (TLSv1.0/1.1)",
            "description": "Server supports TLS 1.0 and/or TLS 1.1 which are deprecated protocols. While not immediately exploitable, they lack modern security features and are prohibited by compliance standards like PCI DSS 4.0.",
            "evidence": "TLSv1.0   enabled\nTLSv1.1   enabled",
            "cwe": "CWE-327",
            "cvss_score": 3.7,
            "remediation": "Configure Apache to use only TLS 1.2 and 1.3:\nSSLProtocol -all +TLSv1.2 +TLSv1.3"
        })
    
    return findings


def print_findings(findings: list[dict], method: str):
    """Pretty print findings"""
    print(f"\n{'='*80}")
    print(f"  {method}")
    print(f"{'='*80}")
    
    if not findings:
        print("  ❌ No findings detected")
        return
    
    for i, finding in enumerate(findings, 1):
        print(f"\n  Finding #{i}")
        print(f"  ├─ Severity: {finding['severity'].upper()}")
        print(f"  ├─ Title: {finding['title']}")
        print(f"  ├─ CWE: {finding.get('cwe', 'N/A')}")
        if 'cvss_score' in finding:
            print(f"  ├─ CVSS Score: {finding['cvss_score']}")
        if 'exploit_available' in finding:
            print(f"  ├─ Exploit Available: {'Yes' if finding['exploit_available'] else 'No'}")
        print(f"  ├─ Description: {finding['description'][:100]}...")
        print(f"  └─ Evidence: {finding['evidence'][:80]}...")


def main():
    print("\n" + "="*80)
    print("  DEMO: Detección de Vulnerabilidades SSL/TLS")
    print("  Comparación: Regex (MVP actual) vs. LLM (propuesto)")
    print("="*80)
    
    print("\n📝 Output de sslscan:")
    print("-" * 80)
    print(SSLSCAN_OUTPUT[:400] + "...[truncated]")
    
    # Análisis con REGEX (método actual)
    regex_findings = analyze_with_regex(SSLSCAN_OUTPUT)
    print_findings(regex_findings, "🤖 DETECCIÓN CON REGEX (MVP Actual v0.1.3)")
    
    # Análisis con LLM (simulado)
    llm_findings = analyze_with_llm_simulation(SSLSCAN_OUTPUT)
    print_findings(llm_findings, "🧠 DETECCIÓN CON LLM (Propuesto)")
    
    # Comparación
    print(f"\n{'='*80}")
    print("  📊 COMPARACIÓN")
    print(f"{'='*80}")
    print(f"  Findings detectados (REGEX): {len(regex_findings)}")
    print(f"  Findings detectados (LLM):   {len(llm_findings)}")
    print(f"  Diferencia:                   +{len(llm_findings) - len(regex_findings)} findings")
    
    print("\n  ✅ Ventajas del LLM:")
    print("     • Detecta SSLv3/POODLE específicamente (no solo 'SSL issue')")
    print("     • Identifica RC4 cipher débil por nombre")
    print("     • Detecta certificado auto-firmado")
    print("     • Detecta falta de TLS Fallback SCSV")
    print("     • Detecta TLSv1.0/1.1 obsoletos")
    print("     • Proporciona CVEs, CVSS scores, y referencias")
    print("     • Evidence preciso (no truncado)")
    print("     • Remediación paso a paso")
    
    print("\n  ❌ Limitaciones del REGEX:")
    print("     • Solo detecta keywords genéricos ('ssl', 'weak')")
    print("     • No entiende contexto (SSLv3 vs. TLSv1.2)")
    print("     • No diferencia severidades correctamente")
    print("     • Evidence truncado e inútil")
    print("     • No proporciona remediación específica")
    print("     • Muchos falsos negativos")
    
    print("\n" + "="*80)
    print("  🎯 CONCLUSIÓN")
    print("="*80)
    print("  El MVP actual (regex) detectó: 0-1 findings genéricos")
    print("  Un LLM detectaría: 5 findings específicos y accionables")
    print("  Mejora: ~5x más vulnerabilidades detectadas con mayor precisión")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
