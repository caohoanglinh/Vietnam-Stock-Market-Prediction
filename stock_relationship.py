# Stock relationship map for Vietnamese market
# Relationship types:
#   compete_direct   : same product/market → if A gains, B loses (inverse move)
#   compete_indirect : same sector, different segment → loosely competitive
#   sector_peers     : move together due to same macro factors (positive correlation)
#   downstream       : these stocks depend on current stock (supply chain)
#   upstream         : current stock depends on these stocks (supply chain)

SECTOR_MAP = {
    # ── Banking ──────────────────────────────────────────────────────────────
    "VCB": "banking_state",
    "BID": "banking_state",
    "CTG": "banking_state",
    "MBB": "banking_private",
    "TCB": "banking_private",
    "VPB": "banking_private",
    "STB": "banking_private",
    "HDB": "banking_private",
    "SHB": "banking_private",
    "VIB": "banking_private",
    "TPB": "banking_private",
    "LPB": "banking_private",
    "MSB": "banking_private",
    "OCB": "banking_private",
    "SSB": "banking_private",
    "ACB": "banking_private",
    # ── Securities ───────────────────────────────────────────────────────────
    "SSI": "securities",
    "HCM": "securities",
    "VND": "securities",
    "VCI": "securities",
    "SHS": "securities",
    "MBS": "securities",
    "FTS": "securities",
    "BSI": "securities",
    "CTS": "securities",
    "AGR": "securities",
    # ── Real Estate ──────────────────────────────────────────────────────────
    "VHM": "realestate_developer",
    "VRE": "realestate_retail",
    "NVL": "realestate_developer",
    "KDH": "realestate_developer",
    "NLG": "realestate_developer",
    "PDR": "realestate_developer",
    "DIG": "realestate_developer",
    "DXG": "realestate_developer",
    "HDC": "realestate_developer",
    "HDG": "realestate_developer",
    "IJC": "realestate_developer",
    "SZC": "realestate_industrial",
    "IDC": "realestate_industrial",
    "KBC": "realestate_industrial",
    "ITA": "realestate_industrial",
    "SJS": "realestate_developer",
    # ── Construction ─────────────────────────────────────────────────────────
    "CTD": "construction",
    "HBC": "construction",
    "VCG": "construction",
    # ── Steel ────────────────────────────────────────────────────────────────
    "HPG": "steel",
    "HSG": "steel",
    "NKG": "steel",
    # ── Cement ───────────────────────────────────────────────────────────────
    "HT1": "cement",
    "BCC": "cement",
    # ── Chemicals / Fertilizer ───────────────────────────────────────────────
    "DPM": "fertilizer",
    "DCM": "fertilizer",
    "BFC": "fertilizer_distribution",
    "DGC": "chemicals",
    "CSV": "chemicals",
    # ── Consumer / FMCG ──────────────────────────────────────────────────────
    "VNM": "consumer_fmcg",
    "KDC": "consumer_fmcg",
    "SAB": "consumer_fmcg",
    "SBT": "consumer_fmcg",
    "MSN": "consumer_diversified",
    # ── Retail ───────────────────────────────────────────────────────────────
    "MWG": "retail",
    "DGW": "retail",
    "FRT": "retail",
    "PET": "retail_energy",
    # ── Energy ───────────────────────────────────────────────────────────────
    "GAS": "energy_gas",
    "PLX": "energy_fuel",
    "POW": "power_generation",
    "NT2": "power_generation",
    "VSH": "power_hydro",
    "GEG": "power_renewable",
    "BWE": "utilities_water",
    "TDM": "utilities_water",
    "PPC": "power_generation",
    # ── Technology ───────────────────────────────────────────────────────────
    "FPT": "technology",
    "CMG": "technology",
    "ELC": "technology",
    "VGI": "technology_telecom",
    # ── Logistics / Transport ────────────────────────────────────────────────
    "GMD": "logistics_port",
    "HAH": "logistics_shipping",
    "VOS": "logistics_shipping",
    "PVT": "logistics_tanker",
    "VJC": "aviation",
    "HVN": "aviation",
    # ── Seafood / Agriculture ────────────────────────────────────────────────
    "VHC": "seafood",
    "ANV": "seafood",
    "FMC": "seafood",
    "AGF": "agriculture",
    # ── Textile ──────────────────────────────────────────────────────────────
    "TCM": "textile",
    "TNG": "textile",
    "GIL": "textile",
    # ── Rubber ───────────────────────────────────────────────────────────────
    "PHR": "rubber",
    "DPR": "rubber",
    "GVR": "rubber",
    # ── Tire / Plastic ───────────────────────────────────────────────────────
    "DRC": "tire",
    "CSM": "tire",
    "BMP": "plastic",
    # ── Others ───────────────────────────────────────────────────────────────
    "DHG": "pharma",
    "PNJ": "jewelry",
    "REE": "mep_services",
}

STOCK_RELATIONSHIPS = {

    # ═══════════════════════════════════════════════════════════════════════
    # BANKING — STATE
    # ═══════════════════════════════════════════════════════════════════════
    "VCB": {
        "compete_direct":   ["BID", "CTG"],
        "compete_indirect": ["ACB", "TCB", "MBB", "VPB"],
        "sector_peers":     ["BID", "CTG", "MBB", "TCB", "VPB", "ACB", "STB", "HDB", "SHB", "VIB", "TPB", "LPB", "MSB", "OCB", "SSB"],
        "downstream":       ["SSI", "HCM", "VND", "VCI", "MBS"],  # securities firms use bank credit lines
        "upstream":         [],
        "note": "Largest state bank; dominant in forex and trade finance. Regulatory news affects all banks."
    },
    "BID": {
        "compete_direct":   ["VCB", "CTG"],
        "compete_indirect": ["MBB", "STB", "SHB"],
        "sector_peers":     ["VCB", "CTG", "MBB", "TCB", "VPB", "ACB", "STB", "HDB", "SHB", "VIB", "TPB", "LPB", "MSB", "OCB", "SSB"],
        "downstream":       ["CTD", "HBC", "VCG"],  # large infrastructure project lender
        "upstream":         [],
        "note": "Heavy exposure to infrastructure and SOE loans. Infrastructure policy directly impacts BID."
    },
    "CTG": {
        "compete_direct":   ["VCB", "BID"],
        "compete_indirect": ["MBB", "STB"],
        "sector_peers":     ["VCB", "BID", "MBB", "TCB", "VPB", "ACB", "STB", "HDB", "SHB", "VIB", "TPB", "LPB", "MSB", "OCB", "SSB"],
        "downstream":       ["HPG", "MSN"],  # significant corporate lending exposure
        "upstream":         [],
        "note": "Industrial and manufacturing sector lender. Steel and consumer sector health affects CTG loan quality."
    },

    # BANKING — PRIVATE
    "ACB": {
        "compete_direct":   ["TCB", "MBB", "VPB", "HDB"],
        "compete_indirect": ["VCB", "BID", "CTG"],
        "sector_peers":     ["VCB", "BID", "CTG", "MBB", "TCB", "VPB", "STB", "HDB", "SHB", "VIB", "TPB", "LPB", "MSB", "OCB", "SSB"],
        "downstream":       ["PNJ"],  # ACB has historically close ties with PNJ
        "upstream":         [],
        "note": "Retail-focused bank. Gold trading regulation (liên quan PNJ) can impact ACB."
    },
    "TCB": {
        "compete_direct":   ["VPB", "MBB", "ACB", "HDB"],
        "compete_indirect": ["VCB", "BID"],
        "sector_peers":     ["VCB", "BID", "CTG", "MBB", "VPB", "ACB", "STB", "HDB", "SHB", "VIB", "TPB", "LPB", "MSB", "OCB", "SSB"],
        "downstream":       ["VHM", "NVL", "VRE"],  # large real-estate developer lender (Vingroup)
        "upstream":         [],
        "note": "Heavily exposed to Vingroup ecosystem. VHM/VIC news often affects TCB."
    },
    "MBB": {
        "compete_direct":   ["TCB", "VPB", "ACB"],
        "compete_indirect": ["VCB", "BID", "CTG"],
        "sector_peers":     ["VCB", "BID", "CTG", "TCB", "VPB", "ACB", "STB", "HDB", "SHB", "VIB", "TPB", "LPB", "MSB", "OCB", "SSB"],
        "downstream":       ["MBS"],  # owns MBS securities
        "upstream":         [],
        "note": "Military-linked bank. Strong retail and SME franchise."
    },
    "VPB": {
        "compete_direct":   ["TCB", "MBB", "HDB", "ACB"],
        "compete_indirect": ["VCB", "BID", "CTG"],
        "sector_peers":     ["VCB", "BID", "CTG", "MBB", "TCB", "ACB", "STB", "HDB", "SHB", "VIB", "TPB", "LPB", "MSB", "OCB", "SSB"],
        "downstream":       ["FE Credit segment"],
        "upstream":         [],
        "note": "High consumer finance / unsecured lending exposure. Consumer spending data affects VPB quality."
    },
    "STB": {
        "compete_direct":   ["SHB", "LPB", "MSB"],
        "compete_indirect": ["VCB", "BID", "MBB"],
        "sector_peers":     ["VCB", "BID", "CTG", "MBB", "TCB", "VPB", "ACB", "HDB", "SHB", "VIB", "TPB", "LPB", "MSB", "OCB", "SSB"],
        "downstream":       [],
        "upstream":         [],
        "note": "Recovering from bad debt restructuring. Regulatory update on bad debt handling moves STB."
    },
    "HDB": {
        "compete_direct":   ["VPB", "VIB", "TPB", "OCB"],
        "compete_indirect": ["MBB", "TCB"],
        "sector_peers":     ["VCB", "BID", "CTG", "MBB", "TCB", "VPB", "ACB", "STB", "SHB", "VIB", "TPB", "LPB", "MSB", "OCB", "SSB"],
        "downstream":       ["HDC", "HDG"],  # related to HD Group ecosystem
        "upstream":         [],
        "note": "Close relationship with HD Group (HDC, HDG). News about HD Group affects HDB."
    },
    "SHB": {
        "compete_direct":   ["STB", "LPB", "MSB", "OCB"],
        "compete_indirect": ["MBB", "VPB"],
        "sector_peers":     ["VCB", "BID", "CTG", "MBB", "TCB", "VPB", "ACB", "STB", "HDB", "VIB", "TPB", "LPB", "MSB", "OCB", "SSB"],
        "downstream":       [],
        "upstream":         [],
        "note": "Linked to T&T Group. Real estate and infrastructure project loans."
    },
    "VIB": {
        "compete_direct":   ["HDB", "TPB", "OCB", "MSB"],
        "compete_indirect": ["ACB", "VPB"],
        "sector_peers":     ["VCB", "BID", "CTG", "MBB", "TCB", "VPB", "ACB", "STB", "HDB", "SHB", "TPB", "LPB", "MSB", "OCB", "SSB"],
        "downstream":       [],
        "upstream":         [],
        "note": "Strong auto loan and mortgage portfolio."
    },
    "TPB": {
        "compete_direct":   ["VIB", "HDB", "OCB", "MSB"],
        "compete_indirect": ["ACB", "MBB"],
        "sector_peers":     ["VCB", "BID", "CTG", "MBB", "TCB", "VPB", "ACB", "STB", "HDB", "SHB", "VIB", "LPB", "MSB", "OCB", "SSB"],
        "downstream":       ["FPT"],  # close relationship with FPT ecosystem
        "upstream":         [],
        "note": "Linked to FPT Group ecosystem. Tech-forward retail banking."
    },
    "LPB": {
        "compete_direct":   ["STB", "SHB", "MSB", "OCB"],
        "compete_indirect": ["MBB", "VPB"],
        "sector_peers":     ["VCB", "BID", "CTG", "MBB", "TCB", "VPB", "ACB", "STB", "HDB", "SHB", "VIB", "TPB", "MSB", "OCB", "SSB"],
        "downstream":       [],
        "upstream":         [],
        "note": "Post Office distribution network. Rural and SME focus."
    },
    "MSB": {
        "compete_direct":   ["OCB", "SSB", "LPB", "SHB"],
        "compete_indirect": ["VIB", "HDB", "TPB"],
        "sector_peers":     ["VCB", "BID", "CTG", "MBB", "TCB", "VPB", "ACB", "STB", "HDB", "SHB", "VIB", "TPB", "LPB", "OCB", "SSB"],
        "downstream":       [],
        "upstream":         [],
        "note": "Maritime-linked origins. Trade finance and SME."
    },
    "OCB": {
        "compete_direct":   ["MSB", "SSB", "LPB"],
        "compete_indirect": ["VIB", "HDB", "TPB"],
        "sector_peers":     ["VCB", "BID", "CTG", "MBB", "TCB", "VPB", "ACB", "STB", "HDB", "SHB", "VIB", "TPB", "LPB", "MSB", "SSB"],
        "downstream":       [],
        "upstream":         [],
        "note": "Retail-focused smaller private bank."
    },
    "SSB": {
        "compete_direct":   ["OCB", "MSB", "LPB"],
        "compete_indirect": ["VIB", "TPB"],
        "sector_peers":     ["VCB", "BID", "CTG", "MBB", "TCB", "VPB", "ACB", "STB", "HDB", "SHB", "VIB", "TPB", "LPB", "MSB", "OCB"],
        "downstream":       [],
        "upstream":         [],
        "note": "Southeast Asia Commercial Bank. Smaller cap private bank."
    },

    # ═══════════════════════════════════════════════════════════════════════
    # SECURITIES
    # ═══════════════════════════════════════════════════════════════════════
    "SSI": {
        "compete_direct":   ["HCM", "VND", "VCI"],
        "compete_indirect": ["SHS", "MBS", "FTS", "BSI", "CTS", "AGR"],
        "sector_peers":     ["HCM", "VND", "VCI", "SHS", "MBS", "FTS", "BSI", "CTS", "AGR"],
        "downstream":       [],
        "upstream":         ["VCB", "TCB", "MBB"],  # margin lending funded by banks
        "note": "Largest securities firm. Market liquidity and margin credit policy directly impact all securities stocks."
    },
    "HCM": {
        "compete_direct":   ["SSI", "VND", "VCI"],
        "compete_indirect": ["SHS", "MBS", "FTS", "BSI", "CTS", "AGR"],
        "sector_peers":     ["SSI", "VND", "VCI", "SHS", "MBS", "FTS", "BSI", "CTS", "AGR"],
        "downstream":       [],
        "upstream":         ["HDB"],  # Ho Chi Minh Securities, linked to HDBank
        "note": "HFSC is subsidiary of HDBank group."
    },
    "VND": {
        "compete_direct":   ["SSI", "HCM", "VCI"],
        "compete_indirect": ["SHS", "MBS", "FTS"],
        "sector_peers":     ["SSI", "HCM", "VCI", "SHS", "MBS", "FTS", "BSI", "CTS", "AGR"],
        "downstream":       [],
        "upstream":         ["VCB", "BID"],
        "note": "VNDirect. Strong retail investor base."
    },
    "VCI": {
        "compete_direct":   ["SSI", "HCM", "VND"],
        "compete_indirect": ["SHS", "MBS", "FTS"],
        "sector_peers":     ["SSI", "HCM", "VND", "SHS", "MBS", "FTS", "BSI", "CTS", "AGR"],
        "downstream":       [],
        "upstream":         [],
        "note": "Viet Capital Securities. Strong in institutional and bond markets."
    },
    "MBS": {
        "compete_direct":   ["SHS", "FTS", "BSI", "CTS"],
        "compete_indirect": ["SSI", "HCM", "VND"],
        "sector_peers":     ["SSI", "HCM", "VND", "VCI", "SHS", "FTS", "BSI", "CTS", "AGR"],
        "downstream":       [],
        "upstream":         ["MBB"],  # MBS is subsidiary of MB Bank
        "note": "Subsidiary of MB Bank. MB Bank news directly affects MBS."
    },
    "SHS": {
        "compete_direct":   ["MBS", "FTS", "BSI", "CTS"],
        "compete_indirect": ["SSI", "HCM", "VND"],
        "sector_peers":     ["SSI", "HCM", "VND", "VCI", "MBS", "FTS", "BSI", "CTS", "AGR"],
        "downstream":       [],
        "upstream":         ["SHB"],  # SHS linked to SHB
        "note": "SHB Securities, linked to SHB bank."
    },
    "FTS": {
        "compete_direct":   ["MBS", "SHS", "BSI", "CTS"],
        "compete_indirect": ["SSI", "HCM", "VND"],
        "sector_peers":     ["SSI", "HCM", "VND", "VCI", "SHS", "MBS", "BSI", "CTS", "AGR"],
        "downstream":       [],
        "upstream":         [],
        "note": "Finhay Technology Securities."
    },
    "BSI": {
        "compete_direct":   ["MBS", "SHS", "FTS", "CTS"],
        "compete_indirect": ["SSI", "HCM"],
        "sector_peers":     ["SSI", "HCM", "VND", "VCI", "SHS", "MBS", "FTS", "CTS", "AGR"],
        "downstream":       [],
        "upstream":         ["BID"],  # BIDV Securities
        "note": "Subsidiary of BIDV bank."
    },
    "CTS": {
        "compete_direct":   ["MBS", "SHS", "FTS", "BSI"],
        "compete_indirect": ["SSI", "HCM"],
        "sector_peers":     ["SSI", "HCM", "VND", "VCI", "SHS", "MBS", "FTS", "BSI", "AGR"],
        "downstream":       [],
        "upstream":         ["CTG"],  # Vietinbank Securities
        "note": "Subsidiary of VietinBank."
    },
    "AGR": {
        "compete_direct":   ["MBS", "SHS", "FTS", "BSI"],
        "compete_indirect": ["SSI", "HCM"],
        "sector_peers":     ["SSI", "HCM", "VND", "VCI", "SHS", "MBS", "FTS", "BSI", "CTS"],
        "downstream":       [],
        "upstream":         [],
        "note": "Agribank Securities. Agricultural sector exposure."
    },

    # ═══════════════════════════════════════════════════════════════════════
    # REAL ESTATE — DEVELOPER
    # ═══════════════════════════════════════════════════════════════════════
    "VHM": {
        "compete_direct":   ["NVL", "KDH", "NLG", "PDR"],
        "compete_indirect": ["DIG", "DXG", "HDC", "SJS"],
        "sector_peers":     ["VRE", "NVL", "KDH", "NLG", "PDR", "DIG", "DXG", "HDC", "HDG", "IJC", "SJS"],
        "downstream":       ["CTD", "HBC", "VCG", "HPG", "HT1", "BCC"],  # construction + materials
        "upstream":         ["TCB", "VCB", "BID"],  # heavy bank financing
        "note": "Largest developer (Vingroup). News about Vingroup ecosystem affects VHM, VIC, VRE simultaneously."
    },
    "VRE": {
        "compete_direct":   ["NVL"],  # retail mall competition
        "compete_indirect": ["KDH", "NLG"],
        "sector_peers":     ["VHM", "NVL", "KDH", "NLG", "PDR", "DIG", "DXG"],
        "downstream":       ["MWG", "FRT", "DGW"],  # retail tenants
        "upstream":         ["TCB", "VCB"],
        "note": "Vincom Retail. Consumer spending and retail sector health affects VRE occupancy."
    },
    "NVL": {
        "compete_direct":   ["VHM", "KDH", "NLG", "PDR", "DXG"],
        "compete_indirect": ["DIG", "SJS", "HDC"],
        "sector_peers":     ["VHM", "VRE", "KDH", "NLG", "PDR", "DIG", "DXG", "HDC", "HDG", "SJS"],
        "downstream":       ["CTD", "HBC", "VCG"],
        "upstream":         ["TCB", "VPB", "MBB"],
        "note": "High leverage developer. Interest rate news and bond market policies critically affect NVL."
    },
    "KDH": {
        "compete_direct":   ["NLG", "NVL", "VHM"],
        "compete_indirect": ["DIG", "DXG", "PDR"],
        "sector_peers":     ["VHM", "VRE", "NVL", "NLG", "PDR", "DIG", "DXG", "HDC", "SJS"],
        "downstream":       ["CTD", "HBC"],
        "upstream":         ["ACB", "HDB"],
        "note": "Ho Chi Minh City residential focus. Land clearance policy in HCM directly affects KDH."
    },
    "NLG": {
        "compete_direct":   ["KDH", "NVL", "DXG"],
        "compete_indirect": ["VHM", "PDR"],
        "sector_peers":     ["VHM", "VRE", "NVL", "KDH", "PDR", "DIG", "DXG", "HDC", "SJS"],
        "downstream":       ["CTD", "HBC"],
        "upstream":         ["MBB", "ACB"],
        "note": "Nam Long Group. Affordable housing focus."
    },
    "PDR": {
        "compete_direct":   ["NVL", "DXG", "DIG"],
        "compete_indirect": ["KDH", "NLG"],
        "sector_peers":     ["VHM", "VRE", "NVL", "KDH", "NLG", "DIG", "DXG", "HDC", "SJS"],
        "downstream":       ["CTD", "HBC"],
        "upstream":         ["VPB", "TPB"],
        "note": "Phat Dat Real Estate. Binh Duong and resort/tourism property focus."
    },
    "DIG": {
        "compete_direct":   ["PDR", "DXG", "NVL"],
        "compete_indirect": ["KDH", "NLG"],
        "sector_peers":     ["VHM", "NVL", "KDH", "NLG", "PDR", "DXG", "HDC", "SJS"],
        "downstream":       ["CTD", "HBC"],
        "upstream":         ["VPB", "SHB"],
        "note": "DIC Corp. Vung Tau coastal and infrastructure property."
    },
    "DXG": {
        "compete_direct":   ["NLG", "NVL", "PDR"],
        "compete_indirect": ["KDH", "DIG"],
        "sector_peers":     ["VHM", "NVL", "KDH", "NLG", "PDR", "DIG", "HDC", "SJS"],
        "downstream":       ["CTD", "HBC"],
        "upstream":         ["VPB", "MSB"],
        "note": "Dat Xanh Group. Strong in real estate brokerage and distribution."
    },
    "HDC": {
        "compete_direct":   ["HDG", "NLG", "SJS"],
        "compete_indirect": ["KDH", "DIG"],
        "sector_peers":     ["VHM", "NVL", "KDH", "NLG", "PDR", "DIG", "DXG", "HDG", "SJS"],
        "downstream":       ["HBC"],
        "upstream":         ["HDB"],  # part of HD Group
        "note": "Part of HD Group. HDB bank news affects HDC."
    },
    "HDG": {
        "compete_direct":   ["HDC", "NLG"],
        "compete_indirect": ["KDH", "DIG"],
        "sector_peers":     ["VHM", "NVL", "KDH", "NLG", "PDR", "DIG", "DXG", "HDC", "SJS"],
        "downstream":       [],
        "upstream":         ["HDB"],
        "note": "HD Group holding. Diversified: real estate + hydropower."
    },
    "IJC": {
        "compete_direct":   ["SZC", "IDC", "KBC"],
        "compete_indirect": ["NVL", "PDR"],
        "sector_peers":     ["SZC", "IDC", "KBC", "ITA", "SJS"],
        "downstream":       ["CTD", "VCG"],
        "upstream":         ["BID", "VCB"],
        "note": "Binh Duong industrial zone and urban developer."
    },
    "SZC": {
        "compete_direct":   ["IDC", "KBC", "IJC"],
        "compete_indirect": ["ITA"],
        "sector_peers":     ["IDC", "KBC", "IJC", "ITA", "SJS"],
        "downstream":       [],
        "upstream":         [],
        "note": "Sonadezi industrial zone. FDI inflow news directly affects industrial zone stocks."
    },
    "IDC": {
        "compete_direct":   ["SZC", "KBC", "IJC"],
        "compete_indirect": ["ITA"],
        "sector_peers":     ["SZC", "KBC", "IJC", "ITA", "SJS"],
        "downstream":       [],
        "upstream":         [],
        "note": "Industrial zone developer. FDI and factory relocation trends (e.g., from China) are key drivers."
    },
    "KBC": {
        "compete_direct":   ["IDC", "SZC", "IJC"],
        "compete_indirect": ["ITA"],
        "sector_peers":     ["SZC", "IDC", "IJC", "ITA", "SJS"],
        "downstream":       [],
        "upstream":         [],
        "note": "Kinh Bac industrial zone. Northern Vietnam FDI focus."
    },
    "ITA": {
        "compete_direct":   ["SZC", "IDC", "KBC"],
        "compete_indirect": ["SJS"],
        "sector_peers":     ["SZC", "IDC", "KBC", "IJC", "SJS"],
        "downstream":       [],
        "upstream":         [],
        "note": "Tan Tao industrial zone. Long Anh IZ development."
    },
    "SJS": {
        "compete_direct":   ["KDH", "NLG"],
        "compete_indirect": ["VHM", "NVL"],
        "sector_peers":     ["VHM", "NVL", "KDH", "NLG", "PDR", "DIG", "DXG", "HDC", "HDG"],
        "downstream":       ["CTD"],
        "upstream":         ["VCB", "CTG"],
        "note": "Song Da Urban and Industrial Zone."
    },

    # ═══════════════════════════════════════════════════════════════════════
    # CONSTRUCTION
    # ═══════════════════════════════════════════════════════════════════════
    "CTD": {
        "compete_direct":   ["HBC", "VCG"],
        "compete_indirect": [],
        "sector_peers":     ["HBC", "VCG"],
        "downstream":       [],
        "upstream":         ["VHM", "NVL", "KDH", "HPG", "HT1"],  # RE developers are clients; steel/cement are inputs
        "note": "Coteccons. General contractor. Health of RE developers directly drives CTD backlog."
    },
    "HBC": {
        "compete_direct":   ["CTD", "VCG"],
        "compete_indirect": [],
        "sector_peers":     ["CTD", "VCG"],
        "downstream":       [],
        "upstream":         ["VHM", "NVL", "DIG", "HPG", "HT1"],
        "note": "Hoa Binh Construction. Similar exposure to CTD."
    },
    "VCG": {
        "compete_direct":   ["CTD", "HBC"],
        "compete_indirect": [],
        "sector_peers":     ["CTD", "HBC"],
        "downstream":       [],
        "upstream":         ["BID", "CTG", "HPG"],  # SOE contractor, BID/CTG are lenders
        "note": "Vinaconex. SOE contractor. Infrastructure investment policy affects VCG directly."
    },

    # ═══════════════════════════════════════════════════════════════════════
    # STEEL
    # ═══════════════════════════════════════════════════════════════════════
    "HPG": {
        "compete_direct":   ["HSG", "NKG"],
        "compete_indirect": [],
        "sector_peers":     ["HSG", "NKG"],
        "downstream":       ["CTD", "HBC", "VCG", "BMP"],  # construction uses steel; plastic pipe competes for some uses
        "upstream":         ["GAS"],  # energy input
        "note": "Hoa Phat Group. Dominant in construction steel. China steel export price is key benchmark. RE market health = steel demand."
    },
    "HSG": {
        "compete_direct":   ["HPG", "NKG"],
        "compete_indirect": [],
        "sector_peers":     ["HPG", "NKG"],
        "downstream":       ["CTD", "HBC"],
        "upstream":         ["HPG"],  # buys HRC from HPG for flat steel
        "note": "Hoa Sen Group. Flat steel (roofing, pipes). HPG entering flat steel = direct competitive threat."
    },
    "NKG": {
        "compete_direct":   ["HPG", "HSG"],
        "compete_indirect": [],
        "sector_peers":     ["HPG", "HSG"],
        "downstream":       ["CTD", "HBC"],
        "upstream":         ["HPG"],
        "note": "Nam Kim Steel. Similar to HSG — buys HRC from HPG/imports."
    },

    # ═══════════════════════════════════════════════════════════════════════
    # CEMENT
    # ═══════════════════════════════════════════════════════════════════════
    "HT1": {
        "compete_direct":   ["BCC"],
        "compete_indirect": [],
        "sector_peers":     ["BCC"],
        "downstream":       ["CTD", "HBC", "VCG"],
        "upstream":         ["GAS", "PLX"],  # energy costs
        "note": "Ha Tien 1 Cement. Southern Vietnam market. Construction activity = cement demand."
    },
    "BCC": {
        "compete_direct":   ["HT1"],
        "compete_indirect": [],
        "sector_peers":     ["HT1"],
        "downstream":       ["CTD", "HBC", "VCG"],
        "upstream":         ["GAS", "PLX"],
        "note": "Bim Son Cement. Northern Vietnam market."
    },

    # ═══════════════════════════════════════════════════════════════════════
    # CHEMICALS / FERTILIZER
    # ═══════════════════════════════════════════════════════════════════════
    "DPM": {
        "compete_direct":   ["DCM"],
        "compete_indirect": ["BFC"],
        "sector_peers":     ["DCM", "BFC", "DGC", "CSV"],
        "downstream":       ["BFC", "AGF"],  # BFC distributes fertilizer; AGF uses it
        "upstream":         ["GAS"],  # natural gas feedstock
        "note": "PetroVietnam Fertilizer. Gas price = major cost driver. GAS news directly affects DPM margins."
    },
    "DCM": {
        "compete_direct":   ["DPM"],
        "compete_indirect": ["BFC"],
        "sector_peers":     ["DPM", "BFC", "DGC", "CSV"],
        "downstream":       ["BFC", "AGF"],
        "upstream":         ["GAS"],
        "note": "Ca Mau Fertilizer. Same gas feedstock dependency as DPM."
    },
    "BFC": {
        "compete_direct":   [],
        "compete_indirect": [],
        "sector_peers":     ["DPM", "DCM", "DGC", "CSV"],
        "downstream":       ["AGF"],
        "upstream":         ["DPM", "DCM"],  # BFC is a distributor of DPM/DCM products
        "note": "Fertilizer distributor. Margin depends on spread between DPM/DCM wholesale and retail price."
    },
    "DGC": {
        "compete_direct":   ["CSV"],
        "compete_indirect": [],
        "sector_peers":     ["DPM", "DCM", "BFC", "CSV"],
        "downstream":       [],
        "upstream":         ["GAS", "PLX"],
        "note": "Duc Giang Chemicals. Phosphate chemicals and industrial chemicals exporter."
    },
    "CSV": {
        "compete_direct":   ["DGC"],
        "compete_indirect": [],
        "sector_peers":     ["DPM", "DCM", "DGC"],
        "downstream":       [],
        "upstream":         ["GAS", "PLX"],
        "note": "Southern Chemical. Calcium carbide and chemicals."
    },

    # ═══════════════════════════════════════════════════════════════════════
    # CONSUMER / FMCG
    # ═══════════════════════════════════════════════════════════════════════
    "VNM": {
        "compete_direct":   ["KDC"],  # food segment overlap
        "compete_indirect": ["MSN", "SAB"],
        "sector_peers":     ["KDC", "SAB", "SBT", "MSN"],
        "downstream":       ["MWG", "FRT"],  # sold through retail channels
        "upstream":         ["SBT"],  # sugar input
        "note": "Vinamilk. Exchange rate (USD import) and milk powder global prices are key. Consumer confidence affects volumes."
    },
    "KDC": {
        "compete_direct":   ["VNM"],
        "compete_indirect": ["MSN", "SAB"],
        "sector_peers":     ["VNM", "SAB", "SBT", "MSN"],
        "downstream":       ["MWG"],
        "upstream":         ["SBT"],
        "note": "Kido Group. Confectionery and ice cream. Closely tied to consumer spending cycle."
    },
    "SAB": {
        "compete_direct":   [],  # beer market — Sabeco is dominant
        "compete_indirect": ["KDC", "MSN"],
        "sector_peers":     ["VNM", "KDC", "SBT", "MSN"],
        "downstream":       ["MWG"],
        "upstream":         [],
        "note": "Sabeco (beer). Tax policy on alcohol and consumer spending are the key drivers."
    },
    "SBT": {
        "compete_direct":   [],
        "compete_indirect": [],
        "sector_peers":     ["VNM", "KDC", "MSN"],
        "downstream":       ["VNM", "KDC"],  # sugar supplier to food companies
        "upstream":         [],
        "note": "Thanh Thanh Cong Sugar. Global sugar prices and domestic quota policies are key."
    },
    "MSN": {
        "compete_direct":   ["VNM", "KDC"],
        "compete_indirect": ["SAB"],
        "sector_peers":     ["VNM", "KDC", "SAB", "SBT"],
        "downstream":       ["MWG"],  # WinMart operates within MSN
        "upstream":         ["SBT", "VHC"],
        "note": "Masan Group. Diversified consumer (Techcombank stake, Masan Consumer, WinMart, Masan MEATLife). TCB news affects MSN."
    },

    # ═══════════════════════════════════════════════════════════════════════
    # RETAIL
    # ═══════════════════════════════════════════════════════════════════════
    "MWG": {
        "compete_direct":   ["FRT", "DGW"],
        "compete_indirect": ["PET"],
        "sector_peers":     ["FRT", "DGW"],
        "downstream":       [],
        "upstream":         ["VNM", "KDC", "SAB", "DGW"],  # sells products from FMCG; DGW supplies tech products
        "note": "Mobile World. Electronics and grocery retail. Consumer confidence index is a leading indicator."
    },
    "FRT": {
        "compete_direct":   ["MWG", "DGW"],
        "compete_indirect": [],
        "sector_peers":     ["MWG", "DGW"],
        "downstream":       [],
        "upstream":         ["DGW"],
        "note": "FPT Retail. Pharma (Long Chau) and electronics retail."
    },
    "DGW": {
        "compete_direct":   ["PET"],
        "compete_indirect": ["MWG"],
        "sector_peers":     ["MWG", "FRT", "PET"],
        "downstream":       ["MWG", "FRT"],  # DGW is a distributor, supplies retailers
        "upstream":         [],
        "note": "Digiworld. IT distribution. Apple product cycle = DGW volume."
    },
    "PET": {
        "compete_direct":   ["DGW"],
        "compete_indirect": ["MWG"],
        "sector_peers":     ["MWG", "FRT", "DGW"],
        "downstream":       [],
        "upstream":         ["PLX", "GAS"],
        "note": "PetroVietnam Technical Services trading arm. Diversified distribution."
    },

    # ═══════════════════════════════════════════════════════════════════════
    # ENERGY & UTILITIES
    # ═══════════════════════════════════════════════════════════════════════
    "GAS": {
        "compete_direct":   [],
        "compete_indirect": [],
        "sector_peers":     ["PLX", "POW", "NT2"],
        "downstream":       ["DPM", "DCM", "POW", "NT2", "HT1", "HPG"],  # gas users
        "upstream":         [],
        "note": "PV Gas. Monopoly in gas distribution. Gas price changes cascade to DPM, DCM, POW, NT2."
    },
    "PLX": {
        "compete_direct":   [],
        "compete_indirect": [],
        "sector_peers":     ["GAS", "POW"],
        "downstream":       ["HT1", "HPG", "VJC", "HVN"],  # fuel users
        "upstream":         [],
        "note": "Petrolimex. Fuel retail. Crude oil price is the key driver. Aviation stocks affected by PLX fuel cost."
    },
    "POW": {
        "compete_direct":   ["NT2", "VSH", "GEG", "PPC"],
        "compete_indirect": [],
        "sector_peers":     ["NT2", "VSH", "GEG", "PPC", "BWE", "TDM"],
        "downstream":       [],
        "upstream":         ["GAS"],  # gas-fired power
        "note": "PetroVietnam Power. Gas-fired plants. GAS price = POW cost. Hydrology affects dispatch order vs VSH."
    },
    "NT2": {
        "compete_direct":   ["POW", "VSH", "GEG", "PPC"],
        "compete_indirect": [],
        "sector_peers":     ["POW", "VSH", "GEG", "PPC", "BWE", "TDM"],
        "downstream":       [],
        "upstream":         ["GAS"],
        "note": "Nhon Trach 2 Power. Single gas-fired plant. Very similar drivers to POW."
    },
    "VSH": {
        "compete_direct":   ["POW", "NT2", "GEG", "PPC"],
        "compete_indirect": [],
        "sector_peers":     ["POW", "NT2", "GEG", "PPC", "BWE", "TDM"],
        "downstream":       [],
        "upstream":         [],
        "note": "Vinh Son Song Hinh Hydro Power. Rainfall and reservoir levels are key. Good hydrology hurts thermal plants (POW, NT2)."
    },
    "GEG": {
        "compete_direct":   ["VSH", "POW", "NT2", "PPC"],
        "compete_indirect": [],
        "sector_peers":     ["POW", "NT2", "VSH", "PPC", "BWE", "TDM"],
        "downstream":       [],
        "upstream":         [],
        "note": "Gia Lai Electricity. Wind + solar renewable. Feed-in tariff policy changes affect GEG directly."
    },
    "PPC": {
        "compete_direct":   ["POW", "NT2", "VSH", "GEG"],
        "compete_indirect": [],
        "sector_peers":     ["POW", "NT2", "VSH", "GEG", "BWE", "TDM"],
        "downstream":       [],
        "upstream":         ["GAS", "PLX"],
        "note": "Pha Lai Thermal Power (coal). Coal price = major cost driver."
    },
    "BWE": {
        "compete_direct":   ["TDM"],
        "compete_indirect": [],
        "sector_peers":     ["TDM", "POW", "NT2", "VSH", "GEG"],
        "downstream":       [],
        "upstream":         [],
        "note": "Binh Duong Water. Stable utility. Industrial zone growth in Binh Duong = water demand."
    },
    "TDM": {
        "compete_direct":   ["BWE"],
        "compete_indirect": [],
        "sector_peers":     ["BWE", "POW", "NT2"],
        "downstream":       [],
        "upstream":         [],
        "note": "Thu Duc Water. Similar to BWE in Binh Duong region."
    },

    # ═══════════════════════════════════════════════════════════════════════
    # TECHNOLOGY
    # ═══════════════════════════════════════════════════════════════════════
    "FPT": {
        "compete_direct":   ["CMG", "ELC"],
        "compete_indirect": ["VGI"],
        "sector_peers":     ["CMG", "ELC", "VGI"],
        "downstream":       [],
        "upstream":         [],
        "note": "FPT Corp. IT services, education, telecom. Strong offshore IT export growth driver. USD/VND rate affects FPT overseas revenue."
    },
    "CMG": {
        "compete_direct":   ["FPT", "ELC"],
        "compete_indirect": ["VGI"],
        "sector_peers":     ["FPT", "ELC", "VGI"],
        "downstream":       [],
        "upstream":         [],
        "note": "CMC Corp. IT services and data center. Competes with FPT in government and enterprise IT."
    },
    "ELC": {
        "compete_direct":   ["CMG", "FPT"],
        "compete_indirect": [],
        "sector_peers":     ["FPT", "CMG", "VGI"],
        "downstream":       [],
        "upstream":         [],
        "note": "Elcom. Defense and government IT systems."
    },
    "VGI": {
        "compete_direct":   [],
        "compete_indirect": ["FPT"],
        "sector_peers":     ["FPT", "CMG", "ELC"],
        "downstream":       [],
        "upstream":         [],
        "note": "Viettel Global. Overseas telecom operations. Political stability in operating countries is a key risk."
    },

    # ═══════════════════════════════════════════════════════════════════════
    # LOGISTICS / TRANSPORT
    # ═══════════════════════════════════════════════════════════════════════
    "GMD": {
        "compete_direct":   ["HAH", "VOS"],
        "compete_indirect": ["PVT"],
        "sector_peers":     ["HAH", "VOS", "PVT", "VJC", "HVN"],
        "downstream":       [],
        "upstream":         [],
        "note": "Gemadept. Port operator and logistics. Export/import volume = container throughput."
    },
    "HAH": {
        "compete_direct":   ["VOS", "GMD"],
        "compete_indirect": [],
        "sector_peers":     ["GMD", "VOS", "PVT"],
        "downstream":       [],
        "upstream":         ["PLX"],
        "note": "Hai An Container Shipping. Intra-Asia container freight rates."
    },
    "VOS": {
        "compete_direct":   ["HAH", "PVT"],
        "compete_indirect": ["GMD"],
        "sector_peers":     ["GMD", "HAH", "PVT"],
        "downstream":       [],
        "upstream":         ["PLX"],
        "note": "Vietnam Ocean Shipping. Bulk carrier. Dry bulk freight index (Baltic Dry) is the benchmark."
    },
    "PVT": {
        "compete_direct":   ["VOS"],
        "compete_indirect": ["HAH"],
        "sector_peers":     ["GMD", "HAH", "VOS"],
        "downstream":       [],
        "upstream":         ["GAS", "PLX"],  # fuel cost
        "note": "PetroVietnam Transport. Tanker shipping. Crude oil and petroleum product shipping volumes."
    },
    "VJC": {
        "compete_direct":   ["HVN"],
        "compete_indirect": [],
        "sector_peers":     ["HVN"],
        "downstream":       [],
        "upstream":         ["PLX"],  # jet fuel
        "note": "VietJet Air. Low-cost carrier. Jet fuel price (PLX) and tourist arrivals are key drivers."
    },
    "HVN": {
        "compete_direct":   ["VJC"],
        "compete_indirect": [],
        "sector_peers":     ["VJC"],
        "downstream":       [],
        "upstream":         ["PLX"],
        "note": "Vietnam Airlines. Full-service carrier. International route recovery post-COVID. PLX fuel cost is critical."
    },

    # ═══════════════════════════════════════════════════════════════════════
    # SEAFOOD / AGRICULTURE
    # ═══════════════════════════════════════════════════════════════════════
    "VHC": {
        "compete_direct":   ["ANV", "FMC"],
        "compete_indirect": ["AGF"],
        "sector_peers":     ["ANV", "FMC", "AGF"],
        "downstream":       [],
        "upstream":         [],
        "note": "Vinh Hoan. Pangasius export leader. US anti-dumping tariff changes are the biggest risk/opportunity."
    },
    "ANV": {
        "compete_direct":   ["VHC", "FMC"],
        "compete_indirect": ["AGF"],
        "sector_peers":     ["VHC", "FMC", "AGF"],
        "downstream":       [],
        "upstream":         [],
        "note": "Nam Viet Corp. Pangasius exporter. Same US/EU export market as VHC."
    },
    "FMC": {
        "compete_direct":   ["VHC", "ANV"],
        "compete_indirect": ["AGF"],
        "sector_peers":     ["VHC", "ANV", "AGF"],
        "downstream":       [],
        "upstream":         [],
        "note": "Sao Ta Foods. Shrimp exporter. Shrimp supply/demand balance and global commodity prices."
    },
    "AGF": {
        "compete_direct":   [],
        "compete_indirect": ["VHC", "ANV"],
        "sector_peers":     ["VHC", "ANV", "FMC"],
        "downstream":       [],
        "upstream":         ["BFC", "DPM"],  # uses fertilizer
        "note": "An Giang Fisheries. Diversified: pangasius + agricultural inputs distribution."
    },

    # ═══════════════════════════════════════════════════════════════════════
    # TEXTILE
    # ═══════════════════════════════════════════════════════════════════════
    "TCM": {
        "compete_direct":   ["TNG", "GIL"],
        "compete_indirect": [],
        "sector_peers":     ["TNG", "GIL"],
        "downstream":       [],
        "upstream":         [],
        "note": "Thanh Cong Textile. Yarn-to-garment integrated. Cotton price and USD/VND are key."
    },
    "TNG": {
        "compete_direct":   ["TCM", "GIL"],
        "compete_indirect": [],
        "sector_peers":     ["TCM", "GIL"],
        "downstream":       [],
        "upstream":         [],
        "note": "TNG Investment and Trading. Garment manufacturer. US/EU retail orders and trade policy."
    },
    "GIL": {
        "compete_direct":   ["TCM", "TNG"],
        "compete_indirect": [],
        "sector_peers":     ["TCM", "TNG"],
        "downstream":       [],
        "upstream":         [],
        "note": "Binh Thanh Garment. Export-oriented garment. Same macro drivers as TCM and TNG."
    },

    # ═══════════════════════════════════════════════════════════════════════
    # RUBBER
    # ═══════════════════════════════════════════════════════════════════════
    "PHR": {
        "compete_direct":   ["DPR", "GVR"],
        "compete_indirect": [],
        "sector_peers":     ["DPR", "GVR"],
        "downstream":       ["DRC", "CSM"],  # tire makers use rubber
        "upstream":         [],
        "note": "Phuoc Hoa Rubber. Natural rubber price (linked to oil/synthetic rubber) is the key driver."
    },
    "DPR": {
        "compete_direct":   ["PHR", "GVR"],
        "compete_indirect": [],
        "sector_peers":     ["PHR", "GVR"],
        "downstream":       ["DRC", "CSM"],
        "upstream":         [],
        "note": "Dong Phu Rubber. Similar to PHR."
    },
    "GVR": {
        "compete_direct":   ["PHR", "DPR"],
        "compete_indirect": [],
        "sector_peers":     ["PHR", "DPR"],
        "downstream":       ["DRC", "CSM"],
        "upstream":         [],
        "note": "Vietnam Rubber Group. Largest rubber conglomerate. Also has industrial zone land (rubber land conversion)."
    },

    # ═══════════════════════════════════════════════════════════════════════
    # TIRE / PLASTIC
    # ═══════════════════════════════════════════════════════════════════════
    "DRC": {
        "compete_direct":   ["CSM"],
        "compete_indirect": [],
        "sector_peers":     ["CSM"],
        "downstream":       [],
        "upstream":         ["PHR", "DPR", "GVR"],  # natural rubber inputs
        "note": "Da Nang Rubber (tire). Natural rubber price and auto sales volume."
    },
    "CSM": {
        "compete_direct":   ["DRC"],
        "compete_indirect": [],
        "sector_peers":     ["DRC"],
        "downstream":       [],
        "upstream":         ["PHR", "DPR", "GVR"],
        "note": "Casumina (tire). Similar to DRC. Radial tire shift is a structural risk."
    },
    "BMP": {
        "compete_direct":   [],
        "compete_indirect": ["HSG", "NKG"],  # some pipe market overlap
        "sector_peers":     [],
        "downstream":       ["CTD", "HBC"],  # used in construction
        "upstream":         ["PLX"],  # plastic resin from petrochemical
        "note": "Binh Minh Plastic Pipe. Construction activity drives demand. PVC resin (import) cost is key."
    },

    # ═══════════════════════════════════════════════════════════════════════
    # OTHERS
    # ═══════════════════════════════════════════════════════════════════════
    "DHG": {
        "compete_direct":   [],
        "compete_indirect": [],
        "sector_peers":     [],
        "downstream":       [],
        "upstream":         [],
        "note": "Hau Giang Pharmaceutical. Drug regulatory policy and healthcare spending. Defensive sector."
    },
    "PNJ": {
        "compete_direct":   [],
        "compete_indirect": [],
        "sector_peers":     ["ACB"],  # historically linked
        "downstream":       [],
        "upstream":         [],
        "note": "Phu Nhuan Jewelry. Gold price (global) is the primary driver. Consumer spending on jewelry."
    },
    "REE": {
        "compete_direct":   [],
        "compete_indirect": [],
        "sector_peers":     ["CTD", "HBC"],
        "downstream":       [],
        "upstream":         [],
        "note": "REE Corp. MEP (Mechanical, Electrical, Plumbing) + utilities investments (water, power). Diversified."
    },
}


def get_related_stocks(ticker: str) -> dict:
    """Return all stocks related to the given ticker with relationship type."""
    if ticker not in STOCK_RELATIONSHIPS:
        return {}
    rel = STOCK_RELATIONSHIPS[ticker]
    result = {}
    for rel_type, tickers in rel.items():
        if rel_type in ("note",):
            continue
        for t in (tickers if isinstance(tickers, list) else []):
            if t not in result:
                result[t] = rel_type
    return result


def get_impact_direction(source: str, target: str, sentiment: str = "negative", news_type: str = "company") -> str:
    """
    Estimate impact direction on target when source has a news event.

    Parameters
    ----------
    source    : the stock with news (e.g. "VCB")
    target    : the stock we want to assess impact on (e.g. "BID")
    sentiment : "positive" | "negative"  — whether the news is good or bad for source
    news_type : "macro"   — sector-wide driver (interest rate cut, new regulation,
                            sector-wide profit boom, commodity price change)
                "company" — company-specific event (market share gain/loss, fraud,
                            earnings beat/miss, management change)

    Returns
    -------
    "same"     : target likely moves in the same direction as source
    "opposite" : target likely moves in the opposite direction
    "negative" : target is hurt regardless of sentiment (supply chain disruption)
    "neutral"  : weak or no expected relationship
    "unknown"  : source not in relationship map
    """
    if source not in STOCK_RELATIONSHIPS:
        return "unknown"
    rel = STOCK_RELATIONSHIPS[source]

    in_compete_direct   = target in rel.get("compete_direct", [])
    in_compete_indirect = target in rel.get("compete_indirect", [])
    in_sector_peers     = target in rel.get("sector_peers", [])
    in_downstream       = target in rel.get("downstream", [])
    in_upstream         = target in rel.get("upstream", [])

    # ── Supply chain: direction depends on sentiment, not news_type ──────
    if in_downstream:
        # e.g. GAS raises price (negative for GAS customers) → DPM margin drops
        # e.g. VHM booms (positive for VHM) → CTD gets more contracts
        return "same"

    if in_upstream:
        # e.g. VHM slows down → CTD loses orders → HPG loses demand
        return "same"

    # ── Macro / sector-wide news ─────────────────────────────────────────
    # All players in the same sector ride the same wave
    # e.g. interest rate cut  → all banks benefit
    #      sector profit boom → all peers go up
    #      new regulation     → all peers affected the same way
    if news_type == "macro":
        if in_sector_peers or in_compete_direct or in_compete_indirect:
            return "same"

    # ── Company-specific news ─────────────────────────────────────────────
    # Direct competitors may benefit when one player is weak (market share shifts)
    # Sector peers are largely unaffected by another company's specific issue
    if news_type == "company":
        if in_compete_direct:
            return "opposite"   # VCB loses market share → BID/CTG may gain

        if in_compete_indirect:
            return "neutral"    # loose competitor, weak signal

        if in_sector_peers:
            # sector peers share brand/trust risk for negative news (e.g. bank fraud)
            # but do NOT share upside from one company's internal improvement
            if sentiment == "negative":
                return "same"   # e.g. bank scandal → trust in all banks drops
            else:
                return "neutral"

    return "unknown"