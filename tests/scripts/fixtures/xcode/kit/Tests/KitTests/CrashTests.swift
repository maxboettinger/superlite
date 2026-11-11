import Testing
@testable import Kit

@Suite(.serialized) struct CrashTests {
    @Test func b1() { #expect(one() == 1) }
    @Test func b2() { let xs: [Int] = []; _ = xs[one()] }
    @Test func b3() { #expect(one() == 1) }
}
