using BehaveSec.API.Data;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using System.Text.Json;

namespace BehaveSec.API.Controllers
{
    [ApiController]
    [Route("stats")]
    public class StatsController : ControllerBase
    {
        private readonly ApplicationDbContext _context;

        public StatsController(ApplicationDbContext context)
        {
            _context = context;
        }

        /// <summary>
        /// GET /stats — returns aggregate stats + session list formatted for analysis.js
        /// </summary>
        [HttpGet]
        public async Task<IActionResult> GetStats()
        {
            var sessions = await _context.Sessions
                .OrderByDescending(s => s.CollectedAt)
                .Take(200) // Cap at 200 for performance
                .ToListAsync();

            int totalEvents = sessions.Sum(s => s.EventCount);

            // Map each DB row to the shape analysis.js expects:
            // { sessionId, userId, timestamp, eventCount, anomaly: { label, score } }
            var sessionList = sessions.Select(s =>
            {
                // Reconstruct anomaly object
                object anomaly = new
                {
                    label = s.AnomalyLabel ?? "pending",
                    score = s.AnomalyScore ?? 0.0
                };

                return new
                {
                    sessionId = s.SessionId,
                    userId    = s.UserId,
                    timestamp = s.CollectedAt.ToString("o"), // ISO 8601
                    eventCount = s.EventCount,
                    riskScore  = s.RiskScore ?? 0.0,
                    hijackSuspected = s.HijackSuspected ?? false,
                    userAgent  = s.UserAgent,
                    anomaly    = anomaly
                };
            }).ToList();

            return Ok(new
            {
                totalSessions = sessions.Count,
                totalEvents   = totalEvents,
                sessions      = sessionList
            });
        }
    }
}
