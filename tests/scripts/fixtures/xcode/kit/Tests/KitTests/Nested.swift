import Testing
@testable import Kit

struct Outer {
    @Suite struct Inner {
        @Test func deep() { #expect(one() == 9) }
    }
}
