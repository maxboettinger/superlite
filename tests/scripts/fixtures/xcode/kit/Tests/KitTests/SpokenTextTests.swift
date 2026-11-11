import Testing
@testable import Kit

@Suite struct SpokenTextTests {
    @Test func hugeLineIsLinear() {
        print("WIRE-ENCODING: {\"a\":1}")
        #expect(one() == 2)
    }
    @Test func passes() { #expect(one() == 1) }
    @Test("display name here") func named() { #expect(one() == 3) }
    @Test(arguments: [1, 2]) func param(x: Int) { #expect(x == 1) }
}

@Test func freeFails() { #expect(one() == 5) }
