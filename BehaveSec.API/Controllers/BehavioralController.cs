using BehaveSec.API.Data;
using BehaveSec.API.Hubs;
using BehaveSec.API.Models;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.SignalR;
using Microsoft.EntityFrameworkCore;
using System.Security.Claims;
using System.Text;
using System.Text.Json;

namespace BehaveSec.API.Controllers
{
    [AllowAnonymous]
    [ApiController]
    [Route("")] 
    public class BehavioralController : ControllerBase
    {
        private readonly ApplicationDbContext _context;
        private readonly IHubContext<NotificationHub> _hubContext;
        private readonly HttpClient _httpClient;
        private readonly ILogger<BehavioralController> _logger;

        // Use 127.0.0.1 instead of localhost to avoid IPv6/IPv4 resolution delays or mismatches.
        private const string PythonMicroserviceUrl = "http://127.0.0.1:8000";

        public BehavioralController(
            ApplicationDbContext context, 
            IHubContext<NotificationHub> hubContext,
            ILogger<BehavioralController> logger)
        {
            _context = context;
            _hubContext = hubContext;
            _httpClient = new HttpClient();
            _logger = logger;
        }

        [HttpPost("analyze")] // Frontend challenge calls /analyze
        public async Task<IActionResult> AnalyzeData([FromBody] JsonElement payload)
        {
            try
            {
                var userId = payload.GetProperty("userId").GetString() ?? "unknown";
                var sessionId = payload.GetProperty("sessionId").GetString() ?? "unknown";
                
                // Proxy to Python ML service
                var content = new StringContent(payload.GetRawText(), Encoding.UTF8, "application/json");
                var response = await _httpClient.PostAsync($"{PythonMicroserviceUrl}/analyze", content);
                
                if (!response.IsSuccessStatusCode)
                {
                    var errBody = await response.Content.ReadAsStringAsync();
                    _logger.LogError("Python ML service error: {Status} - {Body}", response.StatusCode, errBody);
                    return StatusCode((int)response.StatusCode, $"ML Engine Error: {errBody}");
                }
                
                var mlResultStr = await response.Content.ReadAsStringAsync();
                var mlResult = JsonSerializer.Deserialize<JsonElement>(mlResultStr);

                // Try to extract some useful stats to save to C# DB
                var anomalyObj = mlResult.GetProperty("anomaly");
                var anomalyLabel = anomalyObj.TryGetProperty("label", out var labOut) ? labOut.GetString() : "pending";
                var anomalyScore = anomalyObj.TryGetProperty("score", out var scoOut) ? scoOut.GetDouble() : 0;

                // Extract event count
                int eventCount = 0;
                if (payload.TryGetProperty("events", out var evArray) && evArray.ValueKind == JsonValueKind.Array)
                    eventCount = evArray.GetArrayLength();

                // Extract metadata
                string? userAgent = null; int? screenW = null; int? screenH = null; int? durationMs = null;
                if (payload.TryGetProperty("metadata", out var meta))
                {
                    if (meta.TryGetProperty("userAgent", out var ua)) userAgent = ua.GetString();
                    if (meta.TryGetProperty("screenWidth", out var sw) && sw.ValueKind == JsonValueKind.Number) screenW = sw.GetInt32();
                    if (meta.TryGetProperty("screenHeight", out var sh) && sh.ValueKind == JsonValueKind.Number) screenH = sh.GetInt32();
                    if (meta.TryGetProperty("sessionDuration", out var sd) && sd.ValueKind == JsonValueKind.Number) durationMs = sd.GetInt32();
                }

                // Create enriched Session record in C# Database
                var session = new Session
                {
                    UserId             = userId,
                    SessionId          = sessionId,
                    EventCount         = eventCount,
                    UserAgent          = userAgent,
                    IpAddress          = HttpContext.Connection.RemoteIpAddress?.ToString(),
                    ScreenWidth        = screenW,
                    ScreenHeight       = screenH,
                    SessionDurationMs  = durationMs,
                    AnomalyLabel       = anomalyLabel,
                    AnomalyScore       = anomalyScore,
                    RiskScore          = anomalyScore
                };

                _context.Sessions.Add(session);
                await _context.SaveChangesAsync();

                // Broadcast to SignalR if someone is listening
                await _hubContext.Clients.All.SendAsync("new_session", new
                {
                    userId = userId,
                    anomalyLabel = anomalyLabel,
                    riskScore = anomalyScore * 100
                });

                // Return exactly what the frontend expects
                return Content(mlResultStr, "application/json");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error processing analyze request");
                return StatusCode(500, ex.Message);
            }
        }

        [HttpPost("model/feedback")]
        public async Task<IActionResult> ModelFeedback([FromBody] JsonElement payload)
        {
            try
            {
                var content = new StringContent(payload.GetRawText(), Encoding.UTF8, "application/json");
                var response = await _httpClient.PostAsync($"{PythonMicroserviceUrl}/model/feedback", content);
                var resultStr = await response.Content.ReadAsStringAsync();
                return Content(resultStr, "application/json");
            }
            catch (Exception ex)
            {
                return StatusCode(500, ex.Message);
            }
        }
    }
}
