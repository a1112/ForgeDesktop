pragma Singleton
import QtQml
QtObject {
    enum Roles {
        AppId = 256,
        IsWindow,
        IsActive,
        IsMaximized,
        IsFullScreen,
        IsMinimized,
        CanSetNoBorder,
        HasNoBorder,
        IsMinimizable,
        IsMaximizable,
        IsClosable,
        WinIdList
    }
}
