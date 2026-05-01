using System;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace BehaveSec.API.Models
{
    [Table("sessions")]
    public class Session
    {
        [Key]
        [Column("id")]
        public string Id { get; set; } = Guid.NewGuid().ToString();

        [Required]
        [Column("user_id")]
        public string UserId { get; set; } = string.Empty;

        [Required]
        [Column("session_id")]
        public string SessionId { get; set; } = string.Empty;

        [Column("collected_at")]
        public DateTime CollectedAt { get; set; } = DateTime.UtcNow;

        [Column("user_agent")]
        public string? UserAgent { get; set; }

        [Column("ip_address")]
        public string? IpAddress { get; set; }

        [Column("screen_width")]
        public int? ScreenWidth { get; set; }

        [Column("screen_height")]
        public int? ScreenHeight { get; set; }

        [Column("session_duration_ms")]
        public int? SessionDurationMs { get; set; }

        [Column("event_count")]
        public int EventCount { get; set; } = 0;

        [Column("event_breakdown")]
        public string? EventBreakdown { get; set; } // Store JSON as string for SQLite

        [Column("events")]
        public string? Events { get; set; } // Store JSON as string for SQLite

        [Column("anomaly_label")]
        public string? AnomalyLabel { get; set; }

        [Column("anomaly_score")]
        public double? AnomalyScore { get; set; }

        [Column("risk_score")]
        public double? RiskScore { get; set; }

        [Column("hijack_suspected")]
        public bool? HijackSuspected { get; set; } = false;
    }
}
