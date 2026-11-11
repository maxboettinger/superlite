import Testing
@testable import Kit

#if os(macOS)
    @Suite struct HALInputCaptureTests {
        @Test func capture() { #expect(one() == 1) }
        @Test func capture2() { #expect(one() == 1) }
    }
#endif
