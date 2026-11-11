import Testing
@testable import Kit

@Suite struct SkipTests {
    @Test(.disabled("not today")) func skipped() { #expect(one() == 1) }
    @Test func a1() { #expect(one() == 1) }
    @Test func a2() { #expect(one() == 1) }
    @Test func a3() { #expect(one() == 1) }
}
