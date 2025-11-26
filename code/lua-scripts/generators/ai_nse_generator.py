#!/usr/bin/env python3
"""
AI-Powered NSE Script Generator for Metascan

Использует LLM для автоматической генерации Nmap NSE скриптов
на основе CVE описания.
"""

import os
import re
import subprocess
import requests
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class CVEData:
    """CVE information structure"""
    cve_id: str
    cvss_score: float
    description: str
    affected_product: str
    affected_versions: list
    vulnerability_type: str
    references: list


class LuaScriptGenerator:
    """
    Генератор NSE скриптов на основе AI
    """
    
    def __init__(self, model_endpoint: str = "http://localhost:8000"):
        """
        Args:
            model_endpoint: URL к LLM API (YandexGPT, OpenAI-compatible)
        """
        self.model_endpoint = model_endpoint
        self.template_path = os.path.join(
            os.path.dirname(__file__), 
            "templates/nse_template.lua"
        )
    
    def fetch_cve_data(self, cve_id: str) -> CVEData:
        """
        Получение данных о CVE из NVD API
        
        Args:
            cve_id: CVE identifier (e.g., "CVE-2024-12345")
        
        Returns:
            CVEData object
        """
        url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            vuln = data['vulnerabilities'][0]['cve']
            
            return CVEData(
                cve_id=cve_id,
                cvss_score=vuln['metrics']['cvssMetricV31'][0]['cvssData']['baseScore'],
                description=vuln['descriptions'][0]['value'],
                affected_product=vuln['configurations'][0]['nodes'][0]['cpeMatch'][0]['criteria'],
                affected_versions=[],  # TODO: Parse from CPE
                vulnerability_type=vuln['weaknesses'][0]['description'][0]['value'],
                references=[ref['url'] for ref in vuln['references']]
            )
        except Exception as e:
            print(f"Error fetching CVE data: {e}")
            return None
    
    def construct_prompt(self, cve_data: CVEData, similar_exploits: str = "") -> str:
        """
        Конструирование prompt для LLM
        
        Args:
            cve_data: CVE information
            similar_exploits: Примеры похожих эксплойтов
        
        Returns:
            Formatted prompt string
        """
        return f"""
You are an expert Nmap NSE script developer and penetration tester.

Task: Generate a complete, production-ready Nmap NSE script to detect {cve_data.cve_id}.

CVE Information:
- ID: {cve_data.cve_id}
- CVSS Score: {cve_data.cvss_score}
- Severity: {'CRITICAL' if cve_data.cvss_score >= 9.0 else 'HIGH' if cve_data.cvss_score >= 7.0 else 'MEDIUM'}
- Description: {cve_data.description}
- Affected: {cve_data.affected_product}
- Vulnerability Type: {cve_data.vulnerability_type}

Similar exploits for reference:
{similar_exploits}

Requirements:
1. Use proper NSE structure:
   - description: Clear explanation of what the script detects
   - author: "Metascan AI Generator"
   - license: "Same as Nmap--See https://nmap.org/book/man-legal.html"
   - categories: {{"vuln", "intrusive"}} or {{"vuln", "safe"}} depending on the check

2. Import necessary libraries:
   - http (for HTTP requests)
   - vulns (for vulnerability reporting)
   - shortport (for port rules)
   - stdnse (for standard NSE utilities)

3. Define portrule:
   - Use shortport.http for web vulnerabilities
   - Use shortport.port_or_service for specific ports

4. Implement action function:
   - Create vuln table with proper structure
   - Send exploit payload or detection probe
   - Check response for vulnerability indicators
   - Set vuln.state to vulns.STATE.VULN if vulnerable
   - Return vulns.Report(vuln)

5. Error handling:
   - Check if response is nil
   - Handle HTTP errors gracefully
   - Return proper vuln report even on errors

6. Code quality:
   - Use Lua best practices
   - Add comments for complex logic
   - Keep code clean and readable

Generate ONLY valid Lua code. Do not include explanations outside code comments.
Wrap the code in ```lua markers.
"""
    
    def generate_script(self, cve_data: CVEData, max_attempts: int = 3) -> Optional[str]:
        """
        Генерация NSE скрипта с валидацией
        
        Args:
            cve_data: CVE information
            max_attempts: Максимальное количество попыток
        
        Returns:
            Generated Lua script or None
        """
        # TODO: Получить similar exploits из vector DB
        similar_exploits = self._get_similar_exploits(cve_data.cve_id)
        
        prompt = self.construct_prompt(cve_data, similar_exploits)
        
        for attempt in range(max_attempts):
            print(f"Attempt {attempt + 1}/{max_attempts}...")
            
            # Генерация через LLM API
            script = self._call_llm(prompt)
            
            if not script:
                print("Failed to generate script")
                continue
            
            # Извлечение кода
            script = self._extract_code(script)
            
            # Валидация синтаксиса
            if self.validate_syntax(script):
                print("✅ Syntax valid")
                return script
            else:
                print("❌ Syntax error, retrying...")
                error_msg = self._get_lua_error(script)
                prompt += f"\n\nPrevious attempt had syntax error: {error_msg}. Fix and retry."
        
        return None
    
    def _call_llm(self, prompt: str) -> Optional[str]:
        """
        Вызов LLM API
        
        Args:
            prompt: Input prompt
        
        Returns:
            Generated text
        """
        try:
            response = requests.post(
                f"{self.model_endpoint}/v1/completions",
                json={
                    "prompt": prompt,
                    "max_tokens": 2048,
                    "temperature": 0.3,
                    "top_p": 0.95,
                    "stop": ["```\n\n"]
                },
                timeout=60
            )
            response.raise_for_status()
            return response.json()['choices'][0]['text']
        except Exception as e:
            print(f"LLM API error: {e}")
            return None
    
    def _extract_code(self, response: str) -> str:
        """
        Извлечение Lua кода из markdown
        
        Args:
            response: LLM response
        
        Returns:
            Extracted Lua code
        """
        match = re.search(r'```lua\n(.*?)\n```', response, re.DOTALL)
        if match:
            return match.group(1)
        return response  # Fallback
    
    def validate_syntax(self, script: str) -> bool:
        """
        Проверка синтаксиса Lua
        
        Args:
            script: Lua script code
        
        Returns:
            True if valid
        """
        try:
            result = subprocess.run(
                ['luac', '-p', '-'],
                input=script.encode(),
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Validation error: {e}")
            return False
    
    def _get_lua_error(self, script: str) -> str:
        """
        Получение сообщения об ошибке
        
        Args:
            script: Lua script
        
        Returns:
            Error message
        """
        try:
            result = subprocess.run(
                ['luac', '-p', '-'],
                input=script.encode(),
                capture_output=True,
                timeout=5
            )
            return result.stderr.decode()
        except:
            return "Unknown error"
    
    def _get_similar_exploits(self, cve_id: str) -> str:
        """
        Получение похожих эксплойтов из vector DB
        
        TODO: Implement vector similarity search
        
        Args:
            cve_id: CVE ID
        
        Returns:
            Similar exploits as text
        """
        # Placeholder
        return """
Example similar exploit (SQL Injection):

local http = require "http"
local shortport = require "shortport"
local vulns = require "vulns"

portrule = shortport.http

action = function(host, port)
  local vuln = {
    title = "SQL Injection Example",
    state = vulns.STATE.NOT_VULN
  }
  
  local payload = "' OR '1'='1"
  local response = http.post(host, port, "/login", 
    {content = "user=admin&pass=" .. payload})
  
  if response and response.status == 200 then
    vuln.state = vulns.STATE.VULN
  end
  
  return vulns.Report(vuln)
end
"""
    
    def save_script(self, script: str, output_path: str):
        """
        Сохранение скрипта в файл
        
        Args:
            script: Generated script
            output_path: Output file path
        """
        with open(output_path, 'w') as f:
            f.write(script)
        print(f"✅ Script saved to: {output_path}")


def main():
    """
    Пример использования
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate Nmap NSE script from CVE ID using AI"
    )
    parser.add_argument(
        "cve_id",
        help="CVE identifier (e.g., CVE-2024-12345)"
    )
    parser.add_argument(
        "--output", "-o",
        default=".",
        help="Output directory (default: current directory)"
    )
    parser.add_argument(
        "--model-endpoint",
        default="http://localhost:8000",
        help="LLM API endpoint"
    )
    
    args = parser.parse_args()
    
    # Инициализация генератора
    generator = LuaScriptGenerator(model_endpoint=args.model_endpoint)
    
    # Получение CVE данных
    print(f"Fetching CVE data for {args.cve_id}...")
    cve_data = generator.fetch_cve_data(args.cve_id)
    
    if not cve_data:
        print("Failed to fetch CVE data")
        return 1
    
    print(f"CVSS Score: {cve_data.cvss_score}")
    print(f"Description: {cve_data.description[:100]}...")
    
    # Генерация скрипта
    print("\nGenerating NSE script...")
    script = generator.generate_script(cve_data)
    
    if not script:
        print("❌ Failed to generate valid script")
        return 1
    
    # Сохранение
    output_file = os.path.join(
        args.output, 
        f"http-vuln-{args.cve_id.lower()}.nse"
    )
    generator.save_script(script, output_file)
    
    print(f"\n✨ Success! Script generated: {output_file}")
    print(f"\nUsage: nmap --script {output_file} <target>")
    
    return 0


if __name__ == "__main__":
    exit(main())
