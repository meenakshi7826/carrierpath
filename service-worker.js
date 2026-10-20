self.addEventListener("push", event => {
    if (!event.data) {
        return;
    }

    const message = event.data.json();
    const target = new URL(message.url || "/", self.location.origin);
    const url = target.origin === self.location.origin ? target.href : self.location.origin;
    event.waitUntil(
        self.registration.showNotification(message.title || "Study reminder", {
            body: message.body || "It's time for your planned study session.",
            data: { url }
        })
    );
});

self.addEventListener("notificationclick", event => {
    event.notification.close();
    const url = event.notification.data.url;
    event.waitUntil(
        self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(clients => {
            const openClient = clients.find(client => client.url.startsWith(self.location.origin));
            if (openClient) {
                return openClient.focus().then(() => openClient.navigate(url));
            }
            return self.clients.openWindow(url);
        })
    );
});
