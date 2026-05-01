using Microsoft.AspNetCore.SignalR;
using System.Collections.Concurrent;

namespace BehaveSec.API.Hubs
{
    public class NotificationHub : Hub
    {
        // Thread-safe map of userId => ConnectionId
        public static readonly ConcurrentDictionary<string, string> UserConnections = new();

        public override Task OnConnectedAsync()
        {
            var userId = Context.GetHttpContext()?.Request.Query["user_id"].ToString();
            if (!string.IsNullOrEmpty(userId))
            {
                UserConnections[userId] = Context.ConnectionId;
            }
            return base.OnConnectedAsync();
        }

        public override Task OnDisconnectedAsync(Exception? exception)
        {
            var item = UserConnections.FirstOrDefault(kvp => kvp.Value == Context.ConnectionId);
            if (item.Key != null)
            {
                UserConnections.TryRemove(item.Key, out _);
            }
            return base.OnDisconnectedAsync(exception);
        }
    }
}
