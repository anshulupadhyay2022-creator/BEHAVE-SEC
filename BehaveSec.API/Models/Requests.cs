using System.ComponentModel.DataAnnotations;
using System.Text.Json.Serialization;

namespace BehaveSec.API.Models
{
    public class RegisterRequest
    {
        [Required]
        public string Email { get; set; } = string.Empty;
        
        
        [Required]
        [JsonPropertyName("full_name")]
        public string FullName { get; set; } = string.Empty;
        
        [Required]
        public string Password { get; set; } = string.Empty;
    }

    public class LoginRequest
    {
        [Required]
        public string Email { get; set; } = string.Empty;
        
        [Required]
        public string Password { get; set; } = string.Empty;
    }

    public class LoginResponse
    {
        public string AccessToken { get; set; } = string.Empty;
        public string TokenType { get; set; } = "bearer";
        public UserDto User { get; set; } = new();
    }

    public class UserDto
    {
        public string Id { get; set; } = string.Empty;
        public string Email { get; set; } = string.Empty;
        public string FullName { get; set; } = string.Empty;
    }
}
