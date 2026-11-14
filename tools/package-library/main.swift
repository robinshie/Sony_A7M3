import SwiftUI
import UniformTypeIdentifiers

enum CameraState: String, CaseIterable, Identifiable {
    case unsure = "不确定"
    case stock = "原厂"
    case r5 = "r5"
    case r6 = "r6"
    case r7 = "r7"
    var id: Self { self }

    var advice: String {
        switch self {
        case .unsure: "Sony 4.04 版本号无法区分原厂和项目修订。请按实际已安装的模块选择。"
        case .stock: "三份 ZIP 都只有创意外观模块，原厂 4.04 没有对应的初装包。"
        case .r5: "r6 以匹配的 r5 为更新基线；r7 的验证基线是 r6。"
        case .r6: "r7 以匹配的 r6 为更新基线，还依赖机内加载器、菜单资源和机身色彩表。"
        case .r7: "r7 是本库收录的最新修订，已安装就无需重复更新。"
        }
    }
}

struct ArchiveDocument: FileDocument {
    static let readableContentTypes: [UTType] = [.zip]
    let data: Data

    init(data: Data) { self.data = data }

    init(configuration: ReadConfiguration) throws {
        guard let data = configuration.file.regularFileContents else {
            throw CocoaError(.fileReadCorruptFile)
        }
        self.data = data
    }

    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper {
        FileWrapper(regularFileWithContents: data)
    }
}

@MainActor
final class LibraryModel: ObservableObject {
    let archives = Dictionary(uniqueKeysWithValues: Revision.allCases.compactMap { revision in
        revision.verifiedArchive().map { (revision, $0) }
    })
    @Published var cameraState = CameraState.unsure
    @Published var isPicking = false
    @Published var isExporting = false
    @Published var isChecking = false
    @Published var results: [CheckResult] = []
    @Published var message: String?
    var exportName = ""
    var exportDocument: ArchiveDocument?
}

struct LibraryView: View {
    @StateObject private var model = LibraryModel()

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            VStack(alignment: .leading, spacing: 4) {
                Text("A7M3 · 发布包工具")
                    .font(.system(size: 28, weight: .semibold))
                Text("ILCE-7M3 / Sony 4.04   ·   v0.01 创意外观实验版")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            archiveLibrary
            cameraCompatibility
            batchCheck
            if let message = model.message {
                Text(message)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
            Text("离线工具，只校验和导出文件。不会连接或写入相机。")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .padding(24)
        .frame(width: 680, alignment: .topLeading)
        .fileImporter(isPresented: $model.isPicking, allowedContentTypes: [.item], allowsMultipleSelection: true) { selection in
            switch selection {
            case .success(let urls): verify(urls)
            case .failure: model.message = "无法打开选中的文件。"
            }
        }
        .fileExporter(
            isPresented: $model.isExporting, document: model.exportDocument,
            contentType: .zip, defaultFilename: model.exportName
        ) { result in
            switch result {
            case .success(let url): model.message = "已导出 \(url.lastPathComponent)"
            case .failure: model.message = "未能导出 ZIP，请检查目标目录。"
            }
        }
    }

    private var archiveLibrary: some View {
        GroupBox {
            VStack(alignment: .leading, spacing: 8) {
                ForEach(Revision.allCases) { revision in
                    if revision != Revision.allCases.first { Divider() }
                    HStack(spacing: 10) {
                        Text(revision.rawValue.uppercased())
                            .font(.callout.monospaced().weight(.semibold))
                            .foregroundStyle(revision == .r7 ? Color.accentColor : Color.secondary)
                            .frame(width: 28, alignment: .leading)
                        VStack(alignment: .leading, spacing: 3) {
                            Text(revision.title).font(.body.weight(.medium))
                            Text(model.archives[revision] == nil ? "缺失或校验失败" : (revision == .r7 ? "库内最新 · SHA-256 匹配" : "历史版 · SHA-256 匹配"))
                                .font(.caption)
                                .foregroundStyle(model.archives[revision] == nil ? Color.orange : Color.secondary)
                        }
                        Spacer()
                        Button("导出 ZIP…") { export(revision) }
                            .disabled(model.archives[revision] == nil)
                            .accessibilityLabel("导出 \(revision.rawValue) ZIP")
                    }
                }
            }
            .padding(.vertical, 5)
        } label: {
            Label("内置发布包", systemImage: "archivebox")
        }
    }

    private var cameraCompatibility: some View {
        VStack(alignment: .leading, spacing: 7) {
            Picker("机身已有版本", selection: $model.cameraState) {
                ForEach(CameraState.allCases) { Text($0.rawValue).tag($0) }
            }
            .pickerStyle(.segmented)
            Text(model.cameraState.advice)
                .font(.callout)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private var batchCheck: some View {
        GroupBox {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("自动识别发布 ZIP、a7fl.so 和加载器回读")
                        .font(.callout)
                        .foregroundStyle(.secondary)
                    Spacer()
                    if !model.results.isEmpty {
                        Button("清空") { model.results.removeAll() }
                            .disabled(model.isChecking)
                    }
                    Button("添加文件…") { model.isPicking = true }
                        .disabled(model.isChecking)
                }
                if model.isChecking {
                    ProgressView("正在校验…").controlSize(.small)
                } else if !model.results.isEmpty {
                    Text("已识别 \(model.results.filter { $0.status.matched }.count) / \(model.results.count) 个文件")
                        .font(.caption)
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 5) {
                            ForEach(model.results.indices, id: \.self) { index in
                                resultRow(model.results[index])
                            }
                        }
                    }
                    .frame(height: min(CGFloat(model.results.count) * 24, 128))
                }
            }
            .padding(.vertical, 5)
        } label: {
            Label("批量核对已有文件", systemImage: "doc.text.magnifyingglass")
        }
    }

    private func resultRow(_ result: CheckResult) -> some View {
        HStack {
            Text(result.filename)
                .lineLimit(1)
                .truncationMode(.middle)
                .textSelection(.enabled)
            Spacer()
            Label(result.status.label, systemImage: result.status.matched ? "checkmark.circle.fill" : "exclamationmark.circle")
                .foregroundStyle(result.status.matched ? Color.primary : Color.orange)
        }
        .font(.callout)
    }

    private func export(_ revision: Revision) {
        guard let archive = model.archives[revision] else { return }
        model.message = nil
        model.exportName = revision.exportName
        model.exportDocument = ArchiveDocument(data: archive)
        model.isExporting = true
    }

    private func verify(_ urls: [URL]) {
        guard !urls.isEmpty else { return }
        model.isChecking = true
        model.message = nil
        Task {
            let results = await Task.detached(priority: .userInitiated) {
                urls.map { url in
                    let scoped = url.startAccessingSecurityScopedResource()
                    defer { if scoped { url.stopAccessingSecurityScopedResource() } }
                    return Verifier.check(url)
                }
            }.value
            model.results.append(contentsOf: results)
            model.isChecking = false
        }
    }
}

struct LibraryApp: App {
    var body: some Scene {
        Window("A7M3 开发工具", id: "library") {
            TabView {
                LibraryView().tabItem { Label("发布包", systemImage: "archivebox") }
                SimulatorView().tabItem { Label("QEMU 仿真", systemImage: "display") }
            }
            .frame(minHeight: 460)
        }
            .windowResizability(.contentSize)
    }
}

let args = CommandLine.arguments.dropFirst()
if args.first == "--catalog" {
    var allMatch = true
    for revision in Revision.allCases {
        let valid = revision.verifiedArchive() != nil
        print("\(revision.rawValue): \(valid ? revision.zip.hash : "missing-or-invalid")")
        allMatch = allMatch && valid
    }
    exit(allMatch ? 0 : 1)
}
if args.count == 3, args.first == "--check",
   let mode = args.dropFirst().first, let path = args.last,
   mode == "auto" || FileKind(rawValue: mode) != nil {
    let result = Verifier.check(URL(fileURLWithPath: path), as: FileKind(rawValue: mode))
    print(result.status.rawValue)
    if let hash = result.hash { print(hash) }
    exit(result.status.matched ? 0 : 1)
}
LibraryApp.main()
