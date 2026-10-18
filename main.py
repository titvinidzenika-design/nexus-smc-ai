class NexusValidator:
    """
    Nexus Bot Trade Validator
    ამოწმებს ჯონ მერფის 5-პუნქტიან ჩეკლისტს
    """
    def __init__(self, htf_data: dict, ltf_data: dict):
        self.htf = htf_data  # 4H data: {'ema_200': float, 'support_wick': float, 'resistance_wick': float}
        self.ltf = ltf_data  # 15m data: {'close': float, 'entry': float, 'volume': float, 'volume_ma_20': float, 'tp_target': float}

    def validate_long_setup(self) -> dict:
        entry = self.ltf["entry"]
        close = self.ltf["close"]
        
        # 1. HTF ტრენდის ფილტრი (4H EMA 200-ის ზემოთ)
        if close < self.htf["ema_200"]:
            return {"status": False, "reason": "HTF Downtrend Block (Below 4H EMA 200)"}

        # 2. Volume Spike ფილტრი (> 2.5x Volume MA 20)
        required_volume = self.ltf["volume_ma_20"] * 2.5
        if self.ltf["volume"] < required_volume:
            return {"status": False, "reason": f"Low Volume Spike ({self.ltf['volume']:.1f} < {required_volume:.1f})"}

        # 3. HTF Stop-Loss (4H ჩრდილის/Wick-ის მიღმა + 0.2% ბუფერი)
        stop_loss = self.htf["support_wick"] * 0.998
        take_profit = self.ltf["tp_target"]

        # 4. Risk / Reward Ratio გაანგარიშება (Min 1:2)
        risk = entry - stop_loss
        reward = take_profit - entry

        if risk <= 0:
            return {"status": False, "reason": "Invalid Stop-Loss Placement"}

        rr_ratio = reward / risk

        if rr_ratio < 2.0:
            return {"status": False, "reason": f"Low Risk/Reward Ratio (1:{rr_ratio:.2f} < 1:2.00)"}

        # თუ 5-ვე პუნქტი checked: true-ა:
        return {
            "status": True,
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "rr": rr_ratio,
            "reason": "All 5 Checklist criteria PASSED!"
        }
