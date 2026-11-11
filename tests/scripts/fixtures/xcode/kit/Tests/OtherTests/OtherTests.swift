import XCTest
import Testing
@testable import Kit

final class LegacyTests: XCTestCase {
    func testOk() { XCTAssertEqual(one(), 1) }
    func testBad() { print("XCT-OUT"); XCTAssertEqual(one(), 2) }
}

@Suite struct OtherSwiftTests {
    @Test func ok() { #expect(one() == 1) }
    @Test func bad() throws { throw CancellationError() }
}
