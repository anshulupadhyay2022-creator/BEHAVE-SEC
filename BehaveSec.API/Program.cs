using BehaveSec.API.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;
using System.Text;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
builder.Services.AddControllers();

// Configure DB Context (SQLite)
var connectionString = builder.Configuration.GetConnectionString("DefaultConnection") 
    ?? "Data Source=behave.db";
builder.Services.AddDbContext<ApplicationDbContext>(options =>
    options.UseSqlite(connectionString));

// Add CORS
builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowAll", builder =>
    {
        builder.AllowAnyOrigin()
               .AllowAnyMethod()
               .AllowAnyHeader();
    });
});

// Configure JWT Authentication
var jwtSecretKey = builder.Configuration["JwtSettings:SecretKey"] ?? "super_secret_temporary_key_replace_me_in_production";
var key = Encoding.ASCII.GetBytes(jwtSecretKey);
builder.Services.AddAuthentication(x =>
{
    x.DefaultAuthenticateScheme = JwtBearerDefaults.AuthenticationScheme;
    x.DefaultChallengeScheme = JwtBearerDefaults.AuthenticationScheme;
})
.AddJwtBearer(x =>
{
    x.RequireHttpsMetadata = false;
    x.SaveToken = true;
    x.TokenValidationParameters = new TokenValidationParameters
    {
        ValidateIssuerSigningKey = true,
        IssuerSigningKey = new SymmetricSecurityKey(key),
        ValidateIssuer = false,
        ValidateAudience = false,
        ClockSkew = TimeSpan.Zero
    };
});

// SignalR for WebSockets
builder.Services.AddSignalR();

// Ensure Database is Created
var app = builder.Build();

using (var scope = app.Services.CreateScope())
{
    var services = scope.ServiceProvider;
    var context = services.GetRequiredService<ApplicationDbContext>();
    context.Database.EnsureCreated();

    // Auto-seed default admin user (mirrors Python backend behaviour)
    if (!context.Users.Any(u => u.Email == "admin@behave.sec"))
    {
        context.Users.Add(new BehaveSec.API.Models.User
        {
            Email    = "admin@behave.sec",
            FullName = "Admin User",
            PasswordHash = BCrypt.Net.BCrypt.HashPassword("password")
        });
        context.SaveChanges();
        Console.WriteLine("[DB] Default admin@behave.sec user created (password: password)");
    }
}

app.UseCors("AllowAll");
app.UseAuthentication();
app.UseAuthorization();

// ── Serve frontend static files ──────────────────────────────────────────────
// Mirrors what the old Python backend did with StaticFiles(directory="frontend")
var frontendPath = Path.Combine(Directory.GetCurrentDirectory(), "..", "frontend");
if (Directory.Exists(frontendPath))
{
    // Default document: open index.html when navigating to http://localhost:5000
    app.UseDefaultFiles(new DefaultFilesOptions
    {
        FileProvider = new Microsoft.Extensions.FileProviders.PhysicalFileProvider(
            Path.GetFullPath(frontendPath)),
        RequestPath = ""
    });

    app.UseStaticFiles(new StaticFileOptions
    {
        FileProvider = new Microsoft.Extensions.FileProviders.PhysicalFileProvider(
            Path.GetFullPath(frontendPath)),
        RequestPath = ""
    });

    Console.WriteLine($"[STATIC] Serving frontend from: {Path.GetFullPath(frontendPath)}");
}
else
{
    Console.WriteLine("[WARN] Frontend directory not found. Static files will not be served.");
}

// ── Health check ─────────────────────────────────────────────────────────────
app.MapGet("/api/health", () => new { status = "healthy", version = "2.0.0", engine = "C# ASP.NET Core" });

// ── API Controllers & SignalR Hub ─────────────────────────────────────────────
app.MapControllers();
app.MapHub<BehaveSec.API.Hubs.NotificationHub>("/ws");

app.Run();
