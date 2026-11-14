import CryptoKit
import Foundation

enum Revision: String, CaseIterable, Identifiable {
    case r7, r6, r5
    var id: Self { self }

    var title: String {
        switch self {
        case .r7: "返回菜单立即显示「完成」"
        case .r6: "保存前确认，可取消"
        case .r5: "增强 FL 和五项拍摄调节"
        }
    }

    var zip: FileFingerprint {
        switch self {
        case .r7: .init(bytes: 35157, hash: "eff0c93cb08a3c739fe0bd93c3b42b971f82bb241b7b208918de11159c41edfb", status: .r7Package)
        case .r6: .init(bytes: 33762, hash: "7882e36a448df3ff7035391b8beecdb5b02c9b3d59749a08c436468d06779e38", status: .r6Package)
        case .r5: .init(bytes: 30742, hash: "2e48101b8577442b2c9459d31b88819423368ee797adbe0bca8255451455cbdc", status: .r5Package)
        }
    }

    var exportName: String { "Sony_A7M3-v0.01-\(rawValue).zip" }

    func verifiedArchive() -> Data? {
        guard let url = Bundle.main.url(forResource: "Sony_A7M3-v0.01-\(rawValue)", withExtension: "zip", subdirectory: "Releases"),
              Verifier.check(url, as: .package).status == zip.status,
              let data = try? Data(contentsOf: url),
              data.count == zip.bytes, Verifier.digest(data) == zip.hash else { return nil }
        return data
    }
}

enum FileKind: String, CaseIterable, Identifiable {
    case package, module, loader
    var id: Self { self }

    var label: String {
        switch self {
        case .package: "发布 ZIP"
        case .module: "a7fl.so 模块回读"
        case .loader: "viewUnified2.so 加载器回读"
        }
    }

    var matches: [FileFingerprint] {
        switch self {
        case .package: Revision.allCases.map(\.zip)
        case .module:
            [
                .init(bytes: 63524, hash: "74d1df6c73ebd7d056ce741a28e3f459fdf2e7c5ac29063527e18b7111a64703", status: .r7Module),
                .init(bytes: 60744, hash: "25d5f6f1f428cfbd92cae46be496b407eb746fbe06a4120215f5f2b87d508f31", status: .r6Module),
                .init(bytes: 55420, hash: "62c85626243e7009d78999ab16568163e9186934ccd820b70c7b3ea08ff7b5d0", status: .r5Module),
            ]
        case .loader:
            [
                .init(bytes: 10854816, hash: "a1c4d8e88f54f71786ff53bc15a59c32a2969a6ffc934ef77728123d8af172a7", status: .knownLoader),
            ]
        }
    }
}

struct FileFingerprint {
    let bytes: Int
    let hash: String
    let status: CheckStatus
}

enum CheckStatus: String {
    case r7Package = "r7-package"
    case r6Package = "r6-package"
    case r5Package = "r5-package"
    case r7Module = "r7-module"
    case r6Module = "r6-module"
    case r5Module = "r5-module"
    case knownLoader = "known-loader"
    case unknown = "unknown"
    case unreadable = "unreadable"

    var label: String {
        switch self {
        case .r7Package: "匹配 r7 发布 ZIP"
        case .r6Package: "匹配 r6 历史 ZIP"
        case .r5Package: "匹配 r5 历史 ZIP"
        case .r7Module: "匹配 r7 模块"
        case .r6Module: "匹配 r6 模块"
        case .r5Module: "匹配 r5 模块"
        case .knownLoader: "匹配已验收机身的加载器"
        case .unknown: "与已知版本不匹配"
        case .unreadable: "无法读取普通文件"
        }
    }

    var matched: Bool {
        switch self {
        case .r7Package, .r6Package, .r5Package, .r7Module, .r6Module, .r5Module, .knownLoader: true
        case .unknown, .unreadable: false
        }
    }
}

struct CheckResult {
    let status: CheckStatus
    let filename: String
    var hash: String? = nil
}

enum Verifier {
    static func digest(_ data: Data) -> String {
        hex(SHA256.hash(data: data))
    }

    private static func hex(_ hash: SHA256.Digest) -> String {
        hash.map { String(format: "%02x", $0) }.joined()
    }

    static func check(_ url: URL, as kind: FileKind? = nil) -> CheckResult {
        let filename = url.lastPathComponent
        let unreadable = CheckResult(status: .unreadable, filename: filename)
        let unknown = CheckResult(status: .unknown, filename: filename)
        guard url.isFileURL else { return unreadable }
        do {
            let values = try url.resourceValues(forKeys: [.isRegularFileKey, .fileSizeKey])
            guard values.isRegularFile == true, let bytes = values.fileSize else { return unreadable }
            let candidates = (kind?.matches ?? FileKind.allCases.flatMap(\.matches)).filter { $0.bytes == bytes }
            guard !candidates.isEmpty else { return unknown }

            // Open without following symlinks, then bound the read to the pinned length.
            let fd = open(url.path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK)
            guard fd >= 0 else { return unreadable }
            let handle = FileHandle(fileDescriptor: fd, closeOnDealloc: true)
            defer { try? handle.close() }
            var statBuffer = stat()
            guard fstat(fd, &statBuffer) == 0, statBuffer.st_mode & S_IFMT == S_IFREG else { return unreadable }
            guard statBuffer.st_size == bytes else { return unknown }

            var remaining = bytes
            var sha256 = SHA256()
            while remaining > 0 {
                guard let data = try handle.read(upToCount: min(remaining, 65536)), !data.isEmpty else { return unknown }
                remaining -= data.count
                sha256.update(data: data)
            }
            guard (try handle.read(upToCount: 1))?.isEmpty != false else { return unknown }
            let hash = hex(sha256.finalize())
            return CheckResult(status: candidates.first { $0.hash == hash }?.status ?? .unknown, filename: filename, hash: hash)
        } catch {
            return unreadable
        }
    }
}
