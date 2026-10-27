import Foundation
import CryptoKit
let args = CommandLine.arguments
let key = try Curve25519.Signing.PublicKey(rawRepresentation: Data(base64Encoded: args[1])!)
let signature = Data(base64Encoded: args[2])!
let archive = try Data(contentsOf: URL(fileURLWithPath: args[3]), options: .mappedIfSafe)
guard key.isValidSignature(signature, for: archive) else {
    fputs("Update archive signature verification failed\n", stderr)
    exit(1)
}
print("Update archive signature verified with the embedded public key")
