import Foundation

public struct Payload: Sendable {}

public final class Client {
    public func send(_ payload: Payload) -> Bool {
        return true
    }
}
