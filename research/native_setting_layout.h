/* Fixed upgrade from the first deployed dual loader to the SettingMenu hook.
 * All old/new bytes and full file hashes remain independently bundle-pinned.
 * Cave A is unchanged but retained as stage zero of the four-range protocol. */
#define NMA_PAGE_OFFSETS {0x214000,0x20d000,0x5b9000}
#define NMA_PATCH_OFFSETS {0x5b9a7c,0x5b9b1c,0x20d068,0x21464a}
#define NMA_JOURNAL "/setting/A7FL.RETARGET"
#define NMA_RECOVERY_JOURNAL "/setting/A7FL.RETARGET.RECOVER"
#define NMA_UNDO_JOURNAL "/setting/A7FL.RETARGET.UNDO"
#define NMA_UNDO_RECOVERY_JOURNAL "/setting/A7FL.RETARGET.UNDO.RECOVER"
