import datetime
import re
from pathlib import Path
from winreg import ConnectRegistry, OpenKey, EnumValue, HKEY_LOCAL_MACHINE

from osu import OsuDb, BeatmapMetadata, Permissions, TimingPoint
from osu.utility import BinaryFile
import time


def get_osu_path():
    string_pattern = re.compile('\"(.+?)\"')
    reg = ConnectRegistry(None, HKEY_LOCAL_MACHINE)
    # get osu! path
    try:
        key = OpenKey(reg, "SOFTWARE\Classes\osu\DefaultIcon")
    except FileNotFoundError:
        return False
    try:
        value = EnumValue(key, 0)[1]
        path = string_pattern.findall(value)[0]
    except IndexError:
        return False
    return Path(path).parent


class SmallOsuDb(OsuDb):
    def __init__(self, filename, reference):
        self.reference = reference
        super().__init__(filename)

    def load(self, filename):
        BinaryFile.__init__(self, filename, 'r')

        self.version = self.readInt()
        self.mapsetCount = self.readInt()
        self.accountUnlocked = self.readByte() != 0
        self.unrestrictionTime = self.readOsuTimestamp()
        self.username = self.readOsuString()
        beatmapCnt = self.readInt()

        self.beatmaps = []

        self.reference.init_progress.emit(beatmapCnt)
        start = time.time()
        for i in range(beatmapCnt):
            self.beatmaps.append(SmallBeatmapMetadata.fromOsuDb(self))

            now = time.time()
            if now - start >= 1 / 15:  # 15 fps update
                start = now
                self.reference.update_progress.emit(i + 1)
        try:
            if self.username:
                self.permissions = Permissions(self.readInt())
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            pass


class SmallBeatmapMetadata(BeatmapMetadata):
    def __init__(self):
        self.hash = ''
        self.beatmapFile = ''

        self.lastPlayed = datetime.datetime(1, 1, 1)
        self.directory = ''

    @classmethod
    def fromOsuDb(cls, osudb):
        self = cls()
        _ = osudb.readOsuString()  # artistA
        _ = osudb.readOsuString()  # artistU
        _ = osudb.readOsuString()  # titleA
        _ = osudb.readOsuString()  # titleU
        _ = osudb.readOsuString()  # creator
        _ = osudb.readOsuString()  # diffName
        _ = osudb.readOsuString()  # audioFile
        self.hash = osudb.readOsuString()
        self.beatmapFile = osudb.readOsuString()

        _ = osudb.readByte()  # state
        _ = osudb.readShort()  # circles
        _ = osudb.readShort()  # sliders
        _ = osudb.readShort()  # spinners
        self.lastEdit = osudb.readOsuTimestamp()  # lastEdit
        _ = osudb.readFloat()  # AR
        _ = osudb.readFloat()  # CS
        _ = osudb.readFloat()  # HP
        _ = osudb.readFloat()  # OD
        _ = osudb.readDouble()  # SV
        for _ in range(4):
            for _ in range(osudb.readInt()):
                _ = int(osudb.readOsuAny())  # mods
                _ = float(osudb.readOsuAny())  # sr
        _ = osudb.readInt()  # drainTime
        _ = osudb.readInt()  # totalTime
        _ = osudb.readInt()  # previewTime

        for _ in range(osudb.readInt()):
            _ = TimingPoint.fromOsuDb(osudb)

        _ = osudb.readInt()  # mapID
        _ = osudb.readInt()  # mapsetID
        _ = osudb.readInt()  # threadID
        for _ in range(4):
            _ = osudb.readByte()
        _ = osudb.readShort()  # offset
        _ = osudb.readFloat()  # stackLeniency
        _ = osudb.readByte()  # mode
        _ = osudb.readOsuString()  # source
        _ = osudb.readOsuString()  # tags
        _ = osudb.readShort()  # onlineOffset
        _ = osudb.readOsuString()  # onlineTitle
        _ = osudb.readByte()  # isNew
        self.lastPlayed = osudb.readOsuTimestamp()
        _ = osudb.readByte()  # osz2
        self.directory = osudb.readOsuString()
        _ = osudb.readOsuTimestamp()  # lastSync
        _ = osudb.readByte()  # disableHitSounds
        _ = osudb.readByte()  # disableSkin
        _ = osudb.readByte()  # disableSb
        _ = osudb.readByte()  # disableVideo
        _ = osudb.readShort()  # bgDim

        _ = osudb.readInt()

        return self
