"""Turkish explanation templates for the AI explanation layer."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Templates mapping
# ---------------------------------------------------------------------------

POINTS_STATUS_TEMPLATE = "Şu ana kadar toplam {total_points} puan kazandınız."

LEADERBOARD_POSITION_RANK_1 = (
    "Liderlik tablosunda 1. sıradasınız! Toplam {total_points} puanınız var."
)

LEADERBOARD_POSITION_TEMPLATE = (
    "Liderlik tablosunda {rank}. sıradasınız. Toplam {total_points} puanınız "
    "var. Bir üst sıradaki kullanıcı ({next_user_id}) ile aranızda "
    "{points_to_next} puan fark var."
)

BADGE_EARNED_TEMPLATE = "Tebrikler! {badge_type} rozetine zaten ulaştınız."

BADGE_REQUIREMENT_TEMPLATE = (
    "{target_badge} rozetine ulaşmak için {required_points} puana "
    "ihtiyacınız var. Şu anda {current_points} puanınız var. "
    "{remaining_points} puan daha kazanmalısınız."
)

REWARD_WON_TEMPLATE = (
    "Challenge {challenge_id} tamamlandı. {reward_date} tarihinde "
    "{points} puan kazandınız."
)

REWARD_NOT_WON_SUPPRESSED_TEMPLATE = (
    "Challenge {challenge_id} koşullarını sağladınız, ancak daha yüksek "
    "öncelikli olan Challenge {selected_challenge_id} ödülü seçildiği için "
    "bu ödül verilemedi (suppressed)."
)

REWARD_NOT_WON_INACTIVE_TEMPLATE = "Challenge {challenge_id} şu anda aktif değil."

REWARD_NOT_WON_CONDITION_TEMPLATE = (
    "Challenge {challenge_id} koşulu ({condition}) sağlanamadı. "
    "Mevcut değerleriniz: {state_values}."
)

REWARD_NOT_WON_NO_STATE_TEMPLATE = (
    "DailyUserState kaydınız bulunamadığı için Challenge {challenge_id} "
    "değerlendirilemedi."
)

UNKNOWN_QUESTION_TEMPLATE = (
    "Sorunuzu tam olarak anlayamadım. Lütfen rozetler, ödüller, puan "
    "durumunuz veya liderlik tablosu hakkındaki sorularınızı Türkçe olarak sorun."
)
