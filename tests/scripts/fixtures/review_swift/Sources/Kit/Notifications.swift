import Foundation

// public struct Hidden: a comment that names a type
public enum NotificationCategory: Sendable {
    case message, reminder
}

public enum NotificationLevel: Sendable {
    case all, none
}

public struct NotificationPreferences: Sendable {
    public func level(for category: NotificationCategory) -> NotificationLevel {
        return .all
    }
}
