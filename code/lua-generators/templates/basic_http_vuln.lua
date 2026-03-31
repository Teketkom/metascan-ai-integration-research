-- Базовый шаблон для HTTP уязвимостей
local shortport = require "shortport"
local http = require "http"
local stdnse = require "stdnse"
local string = require "string"
local vulns = require "vulns"

description = [[
Template for HTTP-based vulnerability detection.
Customize for specific CVE.
]]

author = "Metascan Research Team"
license = "Same as Nmap"
categories = {"vuln", "safe"}

portrule = shortport.http

action = function(host, port)
    local vuln_table = {
        title = "CVE-XXXX-YYYY: Vulnerability Title",
        state = vulns.STATE.NOT_VULN,
        risk_factor = "High",
    }

    local vuln_report = vulns.Report:new(SCRIPT_NAME, host, port)
    
    -- Проверка уязвимости
    local response = http.get(host, port, "/vulnerable-path")
    
    if response and response.status == 200 then
        if string.match(response.body, "vulnerable_pattern") then
            vuln_table.state = vulns.STATE.VULN
            stdnse.debug1("Vulnerability detected!")
        end
    end
    
    return vuln_report:make_output(vuln_table)
end
