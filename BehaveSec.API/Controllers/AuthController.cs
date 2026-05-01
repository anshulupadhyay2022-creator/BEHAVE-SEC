using BehaveSec.API.Data;
using BehaveSec.API.Models;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Microsoft.IdentityModel.Tokens;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;

namespace BehaveSec.API.Controllers
{
    [ApiController]
    [Route("auth")]
    public class AuthController : ControllerBase
    {
        private readonly ApplicationDbContext _context;
        private readonly IConfiguration _configuration;

        public AuthController(ApplicationDbContext context, IConfiguration configuration)
        {
            _context = context;
            _configuration = configuration;
        }

        [HttpPost("register")]
        [HttpPost("signup")]
        public async Task<IActionResult> Register([FromBody] RegisterRequest request)
        {
            if (await _context.Users.AnyAsync(u => u.Email == request.Email))
            {
                return BadRequest(new { detail = "User with this email already exists." });
            }

            var user = new User
            {
                Email = request.Email,
                FullName = request.FullName,
                PasswordHash = BCrypt.Net.BCrypt.HashPassword(request.Password)
            };

            _context.Users.Add(user);
            await _context.SaveChangesAsync();

            var token = GenerateJwt(user);

            return Ok(new
            {
                access_token = token,
                token_type = "bearer",
                user = new { id = user.Id, email = user.Email, full_name = user.FullName }
            });
        }

        // POST /auth/token  — OAuth2-style (used internally)
        // POST /auth/login  — Friendly alias used by frontend login.js
        [HttpPost("token")]
        [HttpPost("login")]
        public async Task<IActionResult> Login([FromBody] LoginRequest request)
        {
            var user = await _context.Users.FirstOrDefaultAsync(u => u.Email == request.Email);
            if (user == null || !BCrypt.Net.BCrypt.Verify(request.Password, user.PasswordHash))
            {
                return Unauthorized(new { detail = "Invalid email or password." });
            }

            if (user.LockedOut)
            {
                return StatusCode(403, new { detail = "Account locked due to anomaly. MFA required." });
            }

            var token = GenerateJwt(user);

            // Return camelCase to match login.js  (data.access_token, data.user.id)
            return Ok(new
            {
                access_token = token,
                token_type = "bearer",
                user = new { id = user.Id, email = user.Email, full_name = user.FullName }
            });
        }

        // POST /auth/verify-challenge — called after behavioral CAPTCHA in login.js
        [HttpPost("verify-challenge")]
        public async Task<IActionResult> VerifyChallenge([FromBody] System.Text.Json.JsonElement payload)
        {
            // Extract credentials
            var email = payload.GetProperty("email").GetString() ?? "";
            var password = payload.GetProperty("password").GetString() ?? "";

            var user = await _context.Users.FirstOrDefaultAsync(u => u.Email == email);
            if (user == null || !BCrypt.Net.BCrypt.Verify(password, user.PasswordHash))
            {
                return Unauthorized(new { detail = "Invalid credentials." });
            }

            // Forward behavioral events to Python ML for identity verification
            // (fire-and-forget — don't block login for this)
            _ = Task.Run(async () =>
            {
                try
                {
                    using var http = new HttpClient();
                    await http.PostAsync("http://localhost:8000/analyze",
                        new StringContent(payload.GetRawText(),
                            System.Text.Encoding.UTF8, "application/json"));
                }
                catch { /* Non-fatal */ }
            });

            var token = GenerateJwt(user);
            return Ok(new
            {
                access_token = token,
                token_type = "bearer",
                user = new { id = user.Id, email = user.Email, full_name = user.FullName }
            });
        }

        private string GenerateJwt(User user)
        {
            var tokenHandler = new JwtSecurityTokenHandler();
            var keyStr = _configuration["JwtSettings:SecretKey"] ?? "super_secret_temporary_key_replace_me_in_production";
            var key = System.Text.Encoding.ASCII.GetBytes(keyStr);
            var tokenDescriptor = new SecurityTokenDescriptor
            {
                Subject = new ClaimsIdentity(new[]
                {
                    new Claim(ClaimTypes.NameIdentifier, user.Id),
                    new Claim(ClaimTypes.Email, user.Email),
                    new Claim(ClaimTypes.Name, user.FullName)
                }),
                Expires = DateTime.UtcNow.AddHours(1),
                SigningCredentials = new SigningCredentials(
                    new SymmetricSecurityKey(key),
                    SecurityAlgorithms.HmacSha256Signature)
            };
            return tokenHandler.WriteToken(tokenHandler.CreateToken(tokenDescriptor));
        }
    }
}
