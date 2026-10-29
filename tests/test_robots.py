from collectors.robots import RobotsRules

UA = "RahnamaHackathonBot/1.0"


def test_wildcard_query_disallow():
    r = RobotsRules("user-agent: *\ndisallow: *?*\nAllow: *.js\n")
    assert r.can_fetch(UA, "https://jobvision.ir/jobs/73596/x")
    assert not r.can_fetch(UA, "https://jobvision.ir/jobs?page=2")


def test_specific_path_and_longest_match():
    r = RobotsRules("User-agent: *\nDisallow: /*?q=\nDisallow: /cv/*\n")
    assert r.can_fetch(UA, "https://karboom.io/jobs?page=2")
    assert not r.can_fetch(UA, "https://karboom.io/jobs?q=python")
    assert not r.can_fetch(UA, "https://karboom.io/cv/123")


def test_consecutive_agents_share_group():
    # RemoteOK's file: '*' and AhrefsBot form one group that disallows everything.
    r = RobotsRules("User-agent: *\nUser-agent: AhrefsBot\nDisallow: /\n")
    assert not r.can_fetch(UA, "https://remoteok.com/api")


def test_allow_wins_tie_and_unavailable_blocks():
    r = RobotsRules("User-agent: *\nDisallow: /a\nAllow: /a\n")
    assert r.can_fetch(UA, "https://x.com/a")
    assert not RobotsRules(None, available=False).can_fetch(UA, "https://x.com/")
    assert RobotsRules(None).can_fetch(UA, "https://x.com/anything")
