import yfinance as yf

def extract_mining_profile(ticker_symbol):
    """
    Parses yfinance metadata and business summaries to extract 
    the exact commodities and operational life-cycle of a mining ticker.
    """
    try:
        # Fetch data from yfinance
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        
        # Pull key data blocks 
        summary = info.get("longBusinessSummary", "")
        industry = info.get("industry", "Unknown")
        revenue = info.get("totalRevenue", 0)
        
        # Fallback handle if revenue returns None
        if revenue is None:
            revenue = 0

        # 1. Map out target commodities / alt names
        commodity_map = {
            "Gold": ["gold", "au-bearing"],
            "Silver": ["silver", "ag-bearing"],
            "Copper": ["copper", "cu-bearing", "chalcopyrite"],
            "Lithium": ["lithium", "spodumene", "brine", "pegmatite"],
            "Iron Ore": ["iron ore", "iron-ore", "hematite", "magnetite"],
            "Nickel": ["nickel", "ni-bearing"],
            "Uranium": ["uranium", "u3o8", "yellowcake", "triuranium"],
            "Zinc": ["zinc", "zn-bearing"],
            "Cobalt": ["cobalt"],
            "Lead": ["lead", "pb-bearing"],
            "Platinum Group Metals": ["platinum", "palladium", "pgm", "pgms"]
        }
        
        detected_commodities = []
        summary_lower = summary.lower()
        
        # find commodity
        for commodity, keywords in commodity_map.items():
            if any(keyword in summary_lower for keyword in keywords):
                detected_commodities.append(commodity)
        
        # If text parsing misses it, check the high-level industry tag as a fallback
        if not detected_commodities and industry in commodity_map:
            detected_commodities.append(industry)
            
        # 2. Classify the Activity Type
        if revenue > 5_000_000:
            activity_type = "Producer (Active Operations & Revenue)"
        else:
            # Check text hooks to separate explorers from near-term builders
            development_hooks = ["feasibility", "permits", "permitting", "construction", "development-stage", "reserve base"]
            if any(hook in summary_lower for hook in development_hooks):
                activity_type = "Developer (Pre-production / Advanced)"
            else:
                activity_type = "Explorer (Early-stage / Drilling)"
                
        return {
            "Ticker": ticker_symbol,
            "YF Generic Industry": industry,
            "Extracted Commodities": detected_commodities if detected_commodities else ["Specialized Minerals / Unspecified"],
            "Activity Type": activity_type,
            "Revenue (TTM)": f"${revenue:,}"
        }
        
    except Exception as e:
        return {"Ticker": ticker_symbol, "Error": f"Could not pull data: {str(e)}"}

# ==========================================
# EXPANDED TEST CASE RUNNER
# ==========================================
if __name__ == "__main__":
    test_tickers = [
        # --- Diversified & Single-Asset Major Producers ---
        "BHP",    # BHP Group (Giant Diversified Major)
        "RIO",    # Rio Tinto (Iron Ore, Copper, Aluminum powerhouse)
        "NEM",    # Newmont Corp (Pure-play Senior Gold Producer)
        "FCX",    # Freeport-McMoRan (Massive global Copper producer)
        
        # --- Energy & Critical Mineral Producers ---
        "CCJ",    # Cameco Corp (Large-scale active Uranium producer)
        "ALB",    # Albemarle Corp (Global Lithium processing giant)
        
        # --- Developers & Advanced Pre-Revenue Plays ---
        "PMETF",  # Patriot Battery Metals (High-grade Lithium developer)
        "NXE",    # NextGen Energy (Advanced tier Uranium developer)
        
        # --- Pure Early-Stage Explorers (Juniors) ---
        "FILOF",  # Filo Corp (Massive Copper/Gold exploration project)
        "ABBRF"   # American Battery Technology Co (Early Lithium exploration)
    ]
    
    print(f"Scanning Yahoo Finance summaries for {len(test_tickers)} commodities...\n")
    for symbol in test_tickers:
        profile = extract_mining_profile(symbol)
        
        print(f"--- [ {profile['Ticker']} ] Profile Analysis ---")
        if "Error" in profile:
            print(profile["Error"])
        else:
            print(f"  Yahoo Industry Group: {profile['YF Generic Industry']}")
            print(f"  Identified Commodities: {', '.join(profile['Extracted Commodities'])}")
            print(f"  Calculated Activity:   {profile['Activity Type']}")
            print(f"  Reported Revenue:      {profile['Revenue (TTM)']}")
        print("\n" + "="*50 + "\n")
