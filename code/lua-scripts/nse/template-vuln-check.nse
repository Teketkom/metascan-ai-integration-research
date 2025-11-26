-- template-vuln-check.nse
-- Template for Metascan vulnerability detection scripts

description = [[
Template for vulnerability detection NSE script.
Customize for specific CVE detection.

Usage:
  nmap --script template-vuln-check.nse <target>
]]

author = "Metascan Security Team"
license = "Same as Nmap--See https://nmap.org/book/man-legal.html"
categories = {"vuln", "safe"}

local http = require "http"
local shortport = require "shortport"
local vulns = require "vulns"
local stdnse = require "stdnse"

-- Port rule: run on HTTP/HTTPS ports
portrule = shortport.http

-- Main action function
action = function(host, port)
  -- Initialize vulnerability table
  local vuln = {
    title = "CVE-YYYY-XXXXX: Vulnerability Title",
    state = vulns.STATE.NOT_VULN,
    risk_factor = "High",
    scores = {
      CVSS = "9.8/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    },
    description = [[
Detailed vulnerability description goes here.

This template checks for a specific vulnerability by:
1. Sending a crafted HTTP request
2. Analyzing the response
3. Determining if the target is vulnerable
]],
    references = {
      'https://nvd.nist.gov/vuln/detail/CVE-YYYY-XXXXX',
      'https://www.exploit-db.com/exploits/XXXXX'
    },
    dates = {
      disclosure = {year = 'YYYY', month = 'MM', day = 'DD'}
    },
    check_results = {}
  }
  
  -- Step 1: Send probe request
  stdnse.debug1("Sending vulnerability probe to %s:%d", host.ip, port.number)
  
  local path = "/api/vulnerable-endpoint"
  local options = {
    header = {
      ["User-Agent"] = "Metascan/1.0 (Nmap NSE)",
      ["Content-Type"] = "application/json"
    }
  }
  
  local response = http.get(host, port, path, options)
  
  -- Step 2: Check if request was successful
  if not response then
    stdnse.debug1("No response received")
    return vulns.Report(vuln)
  end
  
  if not response.status then
    stdnse.debug1("Invalid response")
    return vulns.Report(vuln)
  end
  
  -- Step 3: Analyze response for vulnerability indicators
  stdnse.debug1("Analyzing response (status: %d)", response.status)
  
  -- Check status code
  if response.status == 200 then
    vuln.check_results[#vuln.check_results + 1] = "HTTP 200 OK received"
    
    -- Check response body for indicators
    if response.body then
      -- Example: Check for error messages indicating vulnerability
      if response.body:match("vulnerable_pattern") or
         response.body:match("error.*sql") or
         response.body:match("syntax error") then
        
        vuln.state = vulns.STATE.VULN
        vuln.check_results[#vuln.check_results + 1] = "Vulnerability pattern detected"
        
        -- Extract additional info if available
        local info = response.body:match("info:([^<]+)")
        if info then
          vuln.extra_info = "Extracted: " .. info
        end
      end
    end
  end
  
  -- Step 4: Check response headers
  if response.header then
    local server = response.header['server']
    if server then
      vuln.check_results[#vuln.check_results + 1] = "Server: " .. server
      stdnse.debug1("Server header: %s", server)
    end
  end
  
  -- Step 5: Return vulnerability report
  return vulns.Report(vuln)
end
