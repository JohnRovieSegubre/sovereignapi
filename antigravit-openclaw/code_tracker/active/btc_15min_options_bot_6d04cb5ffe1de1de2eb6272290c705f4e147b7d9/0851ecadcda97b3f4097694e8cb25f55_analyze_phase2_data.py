‘
import pandas as pd
import os
import re

TRADES_FILE = "ab_test_results/ab_test_trades.csv"
STRATEGY_FILE = "strategy_ab_tester.py"

def get_config_descriptions():
    descriptions = {}
    if not os.path.exists(STRATEGY_FILE):
        return descriptions
        
    with open(STRATEGY_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        # Regex to find config definitions and descriptions
        # Matches: "config_name": { ... "description": "some text"
        # This is a rough parser but sufficient for this file structure
        matches = re.finditer(r'"([a-zA-Z0-9_]+)":\s*\{[^}]*"description":\s*"([^"]+)"', content, re.DOTALL)
        for m in matches:
            descriptions[m.group(1)] = m.group(2)
    return descriptions

def analyze_performance():
    if not os.path.exists(TRADES_FILE):
        print("Trades file not found.")
        return

    try:
        df = pd.read_csv(TRADES_FILE)
    except Exception as e:
        print(f"Error reading trades file: {e}")
        return

    if df.empty:
        print("No trades found.")
        return

    descriptions = get_config_descriptions()

    # Calculate metrics
    stats = []
    grouped = df.groupby('config')
    
    for config, data in grouped:
        total_trades = len(data)
        wins = len(data[data['pnl'] > 0])
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        total_pnl = data['pnl'].sum()
        avg_pnl = data['pnl'].mean()
        desc = descriptions.get(config, "N/A")
        
        stats.append({
            "Config": config,
            "Desc": desc,
            "Trades": total_trades,
            "Win Rate": win_rate,  # Keep as float for sorting
            "Total PnL": total_pnl
        })
    
    # Sort by Total PnL descending
    stats.sort(key=lambda x: x["Total PnL"], reverse=True)
    
    # Print Table
    print(f"{'Config':<30} | {'Trades':<6} | {'Win Rate':<8} | {'Total PnL':<10} | {'Description'}")
    print("-" * 100)
    for s in stats:
        print(f"{s['Config']:<30} | {s['Trades']:<6} | {s['Win Rate']:>7.1f}% | ${s['Total PnL']:>8.2f} | {s['Desc']}")

    # Insights
    if stats:
        print("\n### Quick Insights")
        best = stats[0]
        worst = stats[-1]
        
        # Best Win Rate (>10 trades)
        significant = [s for s in stats if s['Trades'] >= 10]
        best_wr = max(significant, key=lambda x: x['Win Rate']) if significant else None
        
        print(f"1. **Top Earner:** {best['Config']} (+${best['Total PnL']:.2f})")
        if best_wr:
            print(f"2. **Highest Win Rate:** {best_wr['Config']} ({best_wr['Win Rate']:.1f}%)")
        print(f"3. **Biggest Loser:** {worst['Config']} (${worst['Total PnL']:.2f})")

if __name__ == "__main__":
    analyze_performance()
) *cascade08)**cascade08*d *cascade08df*cascade08fg *cascade08gj*cascade08jt *cascade08t}*cascade08}Ñ *cascade08Ñï*cascade08ïñ *cascade08ñ°*cascade08°¢ *cascade08¢≥*cascade08≥µ *cascade08µπ*cascade08π∫ *cascade08∫Ω*cascade08Ωæ *cascade08æ‘*cascade08‘’ *cascade08’Á*cascade08ÁË *cascade08Ë˙*cascade08˙˚ *cascade08˚Ä*cascade08ÄÇ *cascade08ÇÜ*cascade08Üá *cascade08á≠*cascade08≠Æ *cascade08Æ∑ *cascade08∑⁄*cascade08⁄› *cascade08›ﬁ *cascade08ﬁŸ*cascade08Ÿ⁄ *cascade08⁄ˆ*cascade08ˆ˜ *cascade08˜í*cascade08íì *cascade08ìî*cascade08îï *cascade08ï›*cascade08›ﬁ *cascade08ﬁâ*cascade08âä *cascade08äî*cascade08îï *cascade08ïñ*cascade08ñó *cascade08óú*cascade08ú¸ *cascade08¸¨	*cascade08¨	ä *cascade08äé*cascade08éè *cascade08èê*cascade08êë *cascade08ëí*cascade08íï *cascade08ïñ*cascade08ñò *cascade08òô*cascade08ôö *cascade08öõ*cascade08õù *cascade08ùü*cascade08ü° *cascade08°¢*cascade08¢§ *cascade08§¶*cascade08¶ß *cascade08ß®*cascade08®™ *cascade08™Ø*cascade08ØÛ *cascade08Ûé*cascade08é÷ *cascade08÷◊*cascade08◊ÿ *cascade08ÿ‹*cascade08‹› *cascade08›ﬂ*cascade08ﬂ‡ *cascade08‡‚*cascade08‚‰ *cascade08‰Â*cascade08ÂË *cascade08ËÌ*cascade08ÌÓ *cascade08ÓÔ*cascade08Ô *cascade08Ò*cascade08ÒÄ *cascade08ÄÖ*cascade08Öå *cascade08åè*cascade08èê *cascade08êë*cascade08ëØ *cascade08Ø∞*cascade08∞¥ *cascade08¥∂*cascade08∂∑ *cascade08∑π*cascade08πª *cascade08ªº*cascade08ºΩ *cascade08Ω¿*cascade08¿¡ *cascade08¡√*cascade08√ƒ *cascade08ƒ»*cascade08»÷ *cascade08÷‰*cascade08‰Â *cascade08ÂÊ*cascade08ÊÁ *cascade08ÁÈ*cascade08ÈÍ *cascade08ÍÔ*cascade08ÔÒ *cascade08Ò˙*cascade08˙˚ *cascade08˚˝*cascade08˝˛ *cascade08˛ˇ*cascade08ˇÄ *cascade08ÄÜ*cascade08Üï *cascade08ïñ*cascade08ñó *cascade08óô*cascade08ôù *cascade08ùû*cascade08û´ *cascade08´¨*cascade08¨≠ *cascade08≠±*cascade08±≤ *cascade08≤≥*cascade08≥∂ *cascade08∂º*cascade08ºΩ *cascade08Ωæ*cascade08æø *cascade08øÃ*cascade08ÃÕ *cascade08ÕŒ*cascade08Œœ *cascade08œ–*cascade08–— *cascade08—”*cascade08”‘ *cascade08‘◊*cascade08◊ÿ *cascade08ÿŸ*cascade08Ÿ⁄ *cascade08⁄ﬁ*cascade08ﬁﬂ *cascade08ﬂ‡*cascade08‡· *cascade08·‚*cascade08‚Ì *cascade08ÌÚ*cascade08ÚÛ *cascade08Ûˆ*cascade08ˆ˜ *cascade08˜˘*cascade08˘˙ *cascade08˙˝*cascade08˝ˇ *cascade08ˇÖ*cascade08Öå *cascade08åê*cascade08êë *cascade08ëï*cascade08ïñ *cascade08ñó*cascade08óò *cascade08ò¢*cascade08¢• *cascade08•¶*cascade08¶ß *cascade08ß©*cascade08©™ *cascade08™´*cascade08´Æ *cascade08ÆØ*cascade08Ø∞ *cascade08∞±*cascade08±ª *cascade08ªº*cascade08º¿ *cascade08¿»*cascade08»  *cascade08 ‘*cascade08‘’ *cascade08’€*cascade08€‹ *cascade08‹›*cascade08›ﬁ *cascade08ﬁﬂ*cascade08ﬂ‡ *cascade08‡Á*cascade08ÁË *cascade08ËÈ*cascade08ÈÍ *cascade08ÍÔ*cascade08ÔÚ *cascade08ÚÛ*cascade08ÛÙ *cascade08Ùı*cascade08ıˆ *cascade08ˆ¸*cascade08¸˝ *cascade08˝Ä*cascade08ÄÅ *cascade08ÅÇ*cascade08ÇÉ *cascade08ÉÖ*cascade08ÖÜ *cascade08Üä*cascade08äã *cascade08ãå*cascade08åé *cascade08éè*cascade08èê *cascade08êö*cascade08öõ *cascade08õú*cascade08úù *cascade08ù¢*cascade08¢£ *cascade08£®*cascade08®™ *cascade08™¨*cascade08¨≤ *cascade08≤µ*cascade08µ∑ *cascade08∑∫*cascade08∫¬ *cascade08¬ƒ*cascade08ƒ« *cascade08«»*cascade08»… *cascade08…À*cascade08ÀÕ *cascade08Õ—*cascade08—¯ *cascade08¯ˇ*cascade08ˇë *cascade08ëó*cascade08óõ *cascade08õú*cascade08úù *cascade08ùû*cascade08ûü *cascade08ü†*cascade08†° *cascade08°¢*cascade08¢£ *cascade08£•*cascade08•∞ *cascade08∞≤*cascade08≤∫ *cascade08∫ª*cascade08ªº *cascade08ºæ*cascade08æ… *cascade08…œ*cascade08œ“ *cascade08“”*cascade08”› *cascade08›ﬁ*cascade08ﬁÏ *cascade08ÏÔ*cascade08ÔÒ *cascade08ÒÙ*cascade08Ùˆ *cascade08ˆ˜*cascade08˜ˇ *cascade08ˇÅ*cascade08ÅÇ *cascade08ÇÉ*cascade08Éõ *cascade08õú*cascade08úù *cascade08ù¢*cascade08¢£ *cascade08£¶*cascade08¶ß *cascade08ß≠*cascade08≠∏ *cascade08∏ª*cascade08ªΩ *cascade08Ωƒ*cascade08ƒ≈ *cascade08≈«*cascade08«» *cascade08»Œ*cascade08Œœ *cascade08œ—*cascade08—“ *cascade08“÷*cascade08÷◊ *cascade08◊Ÿ*cascade08ŸÂ *cascade08ÂË*cascade08ËÈ *cascade08ÈÏ*cascade08ÏÌ *cascade08ÌÑ*cascade08ÑÖ *cascade08Öá*cascade08áà *cascade08àï*cascade08ïñ *cascade08ñò*cascade08òô *cascade08ôü*cascade08ü† *cascade08†°*cascade08°£ *cascade08£§*cascade08§• *cascade08•ß*cascade08ß® *cascade08®©*cascade08©´ *cascade08´º*cascade08ºæ *cascade08æ≈*cascade08≈∆ *cascade08∆÷*cascade08÷◊ *cascade08◊·*cascade08·„ *cascade08„Á*cascade08Á˜ *cascade08˜˘*cascade08˘ë *cascade08ëî*cascade08î¶ *cascade08¶©*cascade08©π *cascade08πΩ*cascade08Ωæ *cascade08æø*cascade08ø‘ *cascade08‘÷*cascade08÷Ÿ *cascade08Ÿﬁ*cascade08ﬁ· *cascade08·‚*cascade08‚„ *cascade08„‰*cascade08‰˝ *cascade08˝˛*cascade08˛ë *cascade08ëï*cascade08ï‘ *cascade08"(6d04cb5ffe1de1de2eb6272290c705f4e147b7d92Mfile:///c:/Users/rovie%20segubre/btc_15min_options_bot/analyze_phase2_data.py:6file:///c:/Users/rovie%20segubre/btc_15min_options_bot